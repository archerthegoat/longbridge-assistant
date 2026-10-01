"""Collect read-only Longbridge facts without logging broker payloads."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone, time
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time as clock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from private_io import MAX_BYTES, SafeError, load_json, lock, private_root, write_json

UTC = timezone.utc
SYMBOL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\.(US|HK|CN|SG)$")
OPTION = re.compile(r"^[A-Za-z0-9_.-]+[0-9]{6}[CP][0-9]+\.US$")
READ_METHODS = {
    "quote.trading_days", "quote.trading_session", "quote.static_info",
    "quote.option_quote", "quote.candlesticks", "trade.order_detail",
}
READ_PATHS = {
    "/v3/trade/execution/all", "/v1/ipo/profile", "/v1/ipo/timeline",
    "/v1/asset/account", "/v1/asset/stock",
    "/v1/portfolio/profit-analysis-summary", "/v1/asset/exchange_rates",
}
ENV_KEYS = {
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PATH", "LANG",
    "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR", "TEMP", "TMP",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTP_PROXY", "HTTPS_PROXY",
    "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy",
}


def moment(value) -> datetime:
    if isinstance(value, (str, int, float)) and re.fullmatch(r"[0-9]+(\.[0-9]+)?", str(value)):
        return datetime.fromtimestamp(float(value), UTC)
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise SafeError("timestamp_timezone_missing")
    return result.astimezone(UTC)


def number(value) -> str | None:
    try:
        result = Decimal(str(value))
        return str(result) if result.is_finite() and result >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def symbol(value) -> str:
    text = str(value)
    if not SYMBOL.fullmatch(text):
        raise SafeError("symbol_invalid")
    return text


def counter(value: str) -> str:
    ticker, market = symbol(value).rsplit(".", 1)
    if market == "HK" and ticker.isdigit():
        ticker = str(int(ticker))
    return f"ST/{market}/{ticker}"


class Provider:
    def __init__(self, binary: str):
        found = shutil.which(binary) if "/" not in binary and "\\" not in binary else binary
        if not found:
            raise SafeError("longbridge_missing")
        self.binary = str(Path(found).resolve(strict=True))
        if os.stat(self.binary).st_mode & 0o002:
            raise SafeError("longbridge_binary_unsafe")
        self.environment = {k: v for k, v in os.environ.items() if k in ENV_KEYS}
        self.environment.update(
            LONGBRIDGE_LOG="off", RUST_LOG="off", RUST_BACKTRACE="0",
            LONGBRIDGE_NO_ANALYTICS="1", DO_NOT_TRACK="1",
            LONGBRIDGE_PRINT_QUOTE_PACKAGES="false", NO_COLOR="1",
        )
        self.work = tempfile.TemporaryDirectory(prefix="longbridge-assistant-")
        os.chmod(self.work.name, 0o700)
        Path(self.work.name, ".env").touch(mode=0o600)
        self.process = None
        try:
            version = self.command(["--version"])
            if not re.search(r"\b0\.28\.0\b", str(version)):
                raise SafeError("cli_version_not_verified")
            self.serial = 0
            self.responses = queue.Queue(maxsize=4)
            self.process = subprocess.Popen(
                [self.binary, "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, cwd=self.work.name, env=self.environment,
            )
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            while True:
                raw = self.process.stdout.readline(MAX_BYTES + 1)
                if not raw:
                    self.responses.put(None)
                    return
                if len(raw) > MAX_BYTES:
                    self.responses.put({"fatal": True})
                    return
                self.responses.put(json.loads(raw))
        except Exception:
            self.responses.put({"fatal": True})

    def command(self, args):
        if args not in [["--version"], ["ipo", "subscriptions", "--format", "json"],
                        ["ipo", "wait-listing", "--format", "json"]]:
            raise SafeError("read_command_not_allowed")
        try:
            result = subprocess.run(
                [self.binary, *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                cwd=self.work.name, env=self.environment, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise SafeError("provider_unavailable")
        if result.returncode or len(result.stdout) > MAX_BYTES:
            raise SafeError("provider_unavailable")
        if args == ["--version"]:
            return result.stdout.decode("utf-8", "strict")
        try:
            return json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise SafeError("provider_schema")

    def call(self, method, params=None):
        params = params or {}
        if method == "api.get":
            path = params.get("path", "")
            if path not in READ_PATHS:
                raise SafeError("read_path_not_allowed")
        elif method not in READ_METHODS:
            raise SafeError("read_method_not_allowed")
        self.serial += 1
        request_id = self.serial
        try:
            self.process.stdin.write((json.dumps({
                "jsonrpc": "2.0", "id": request_id, "method": method, "params": params,
            }) + "\n").encode())
            self.process.stdin.flush()
            deadline = clock.monotonic() + 60
            while True:
                remaining = deadline - clock.monotonic()
                if remaining <= 0:
                    raise SafeError("provider_timeout")
                result = self.responses.get(timeout=remaining)
                if not isinstance(result, dict) or result.get("fatal"):
                    raise SafeError("provider_protocol")
                if result.get("id") != request_id:
                    continue
                if "error" in result:
                    raise SafeError("provider_query_failed")
                return result["result"]
        except (OSError, KeyError, queue.Empty):
            raise SafeError("provider_unavailable")

    def get(self, path, query=None):
        return self.call("api.get", {"path": path, "query": query or {}})

    def close(self):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.work.cleanup()


def module(status="失败", reason="", **fields):
    return {"status": status, "reason": reason, **fields}


def mapping(rows):
    if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
        raise SafeError("quote_schema")
    return {symbol(item["symbol"]): item for item in rows}


def numeric(value):
    try:
        if value is None or str(value).strip()=='':return None
        n=Decimal(str(value));return n if n.is_finite() else None
    except (ValueError,InvalidOperation):return None
def completed_close(provider, ticker, now, calendars, sessions):
    market = ticker.rsplit('.', 1)[-1]
    zones = {'US': 'America/New_York', 'HK': 'Asia/Hong_Kong', 'SG': 'Asia/Singapore'}
    if market not in zones:
        raise SafeError('close_market_unverified')
    zone = ZoneInfo(zones[market])
    today = now.astimezone(zone).date()
    if market not in calendars:
        calendar = provider.call('quote.trading_days', {
            'market': market, 'start': (today - timedelta(days=28)).isoformat(), 'end': today.isoformat(),
        })
        if not isinstance(calendar, dict) or not isinstance(calendar.get('trading_days'), list) or not isinstance(calendar.get('half_trading_days', []), list):
            raise SafeError('close_calendar_schema')
        session = next((item for item in sessions if isinstance(item, dict) and item.get('market') == market), {})
        intraday = [item for item in session.get('trade_sessions', []) if isinstance(item, dict) and item.get('trade_session') == 'Intraday']
        if not intraday:
            raise SafeError('close_session_missing')
        begin = min(time.fromisoformat(item['begin_time']) for item in intraday)
        end = max(time.fromisoformat(item['end_time']) for item in intraday)
        if begin >= end:
            raise SafeError('close_session_invalid')
        half = set(calendar.get('half_trading_days', []))
        # Do not infer today's special half-day closing time from a normal-day schedule.
        if today.isoformat() in half and datetime.combine(today, begin, zone) <= now.astimezone(zone) < datetime.combine(today, end, zone) + timedelta(minutes=30):
            raise SafeError('half_day_close_unverified')
        days = [datetime.fromisoformat(day).date() for day in set(calendar['trading_days']) | half]
        completed = [day for day in days if datetime.combine(day, end, zone).astimezone(UTC) + timedelta(minutes=30) <= now]
        if not completed:
            raise SafeError('completed_close_date_missing')
        calendars[market] = (max(completed), zone)
    day, zone = calendars[market]
    bars = provider.call('quote.candlesticks', {'symbol': ticker, 'period': 'day', 'count': 10, 'adjust': 'none'})
    if not isinstance(bars, list):
        raise SafeError('close_schema')
    matching = []
    for bar in bars:
        if not isinstance(bar, dict) or bar.get('trade_session') != 'Intraday':
            continue
        stamp = moment(bar.get('timestamp'))
        price = numeric(bar.get('close'))
        if stamp.astimezone(zone).date() == day and stamp <= now and price is not None and price > 0:
            matching.append((stamp, price))
    if len(matching) != 1:
        raise SafeError('latest_close_not_verified')
    stamp, price = matching[0]
    return str(price), day.isoformat(), stamp.isoformat()


def collect_daily_pnl(provider, report_day):
    result = {'status': '失败', 'currency': 'USD', 'amount': None, 'report_date': report_day, 'reason': '单日账户盈亏未取得'}
    if not report_day:
        return result
    try:
        day = datetime.fromisoformat(report_day).date()
        start = int(datetime.combine(day, time.min, UTC).timestamp())
        data = provider.get('/v1/portfolio/profit-analysis-summary', {'start': str(start), 'end': str(start + 86399)})
        if not isinstance(data, dict):
            raise SafeError('daily_pnl_schema')
        summary = data.get('summary', data)
        if not isinstance(summary, dict):
            raise SafeError('daily_pnl_schema')
        amount = numeric(summary.get('sum_profit'))
        period = {key: summary.get(key) for key in ['start_date', 'end_date', 'start_time', 'end_time']}
        result['period'] = period
        if summary.get('currency') == 'USD' and period['start_date'] == report_day and period['end_date'] == report_day and amount is not None:
            result.update(status='完整', amount=str(amount), reason='')
        else:
            result['reason'] = '单日日期、USD币种或原始金额未核对'
    except (SafeError, ValueError, TypeError, KeyError, OverflowError, OSError):
        pass
    return result


def sort_holdings(provider, holdings):
    rows = holdings['rows']
    symbols = sorted({row['symbol'] for row in rows if SYMBOL.fullmatch(row['symbol'])})
    infos, options, rates = {}, {}, []
    try:
        if symbols:
            infos = mapping(provider.call('quote.static_info', {'symbols': symbols}))
    except (SafeError, ValueError, TypeError, KeyError):
        pass
    option_symbols = [ticker for ticker in symbols if OPTION.fullmatch(ticker) or infos.get(ticker, {}).get('board') in {'USOption', 'USOptionS'}]
    try:
        if option_symbols:
            options = mapping(provider.call('quote.option_quote', {'symbols': option_symbols}))
    except (SafeError, ValueError, TypeError, KeyError):
        pass
    if any(row.get('currency') not in {None, 'USD'} for row in rows):
        try:
            response = provider.get('/v1/asset/exchange_rates')
            if isinstance(response, dict) and isinstance(response.get('exchanges'), list):
                rates = response['exchanges']
        except (SafeError, ValueError, TypeError, KeyError):
            pass
    spot_boards = {'USMain', 'USPink', 'HKEquity', 'SGMain', 'SHMainConnect', 'SHMainNonConnect', 'SHSTAR', 'SZMainConnect', 'SZMainNonConnect', 'SZGEMConnect', 'SZGEMNonConnect'}
    partial = False
    for row in rows:
        row['sort_amount_usd'] = None
        ticker, currency = row['symbol'], row.get('currency')
        info = infos.get(ticker, {})
        qty, price = numeric(row.get('quantity')), numeric(row.get('close_price'))
        multiplier = numeric(options.get(ticker, {}).get('contract_multiplier')) if ticker in option_symbols and info.get('board') == 'USOption' else Decimal(1) if info.get('board') in spot_boards else None
        row['sort_quantity_basis'] = 'USOption数量按标准合约惯例估算，接口单位未明确声明' if ticker in option_symbols and multiplier is not None else '已核对证券板块的数量'
        if ticker in option_symbols and multiplier is not None:
            partial = True
        factor = Decimal(1) if currency == 'USD' else None
        if factor is None:
            candidates = []
            for rate in rates:
                if not isinstance(rate, dict):
                    continue
                value = numeric(rate.get('average_rate'))
                if value is None or value <= 0:
                    continue
                if rate.get('base_currency') == 'USD' and rate.get('other_currency') == currency:
                    candidates.append(Decimal(1) / value)
                elif rate.get('base_currency') == currency and rate.get('other_currency') == 'USD':
                    candidates.append(value)
            if len(candidates) == 1:
                factor = candidates[0]
        if qty is not None and price is not None and multiplier is not None and multiplier > 0 and factor is not None and info.get('currency') == currency:
            row['sort_amount_usd'] = str(abs(qty * price * multiplier * factor))
            row['sort_multiplier'] = str(multiplier)
        else:
            partial = True
    rows.sort(key=lambda row: (row['sort_amount_usd'] is None, -numeric(row['sort_amount_usd']) if row['sort_amount_usd'] is not None else Decimal(0), row['symbol']))
    holdings['sort_status'] = '部分完成' if partial else '完整'
    return holdings


def collect_snapshot(provider, now, report_day=None):
    balances = {'status': '失败', 'reason': 'USD账户金额未取得', 'rows': []}
    holdings = {'status': '失败', 'reason': '持仓未取得', 'rows': []}
    try:
        data = provider.get('/v1/asset/account', {'currency': 'USD'})
        if not isinstance(data, dict) or not isinstance(data.get('list'), list):
            raise SafeError('balance_schema')
        rows = []
        partial = False
        for item in data['list']:
            if not isinstance(item, dict) or item.get('currency') != 'USD':
                partial = True
                continue
            net, cash = numeric(item.get('net_assets')), numeric(item.get('total_cash'))
            partial = partial or net is None or cash is None
            rows.append({'currency': 'USD', 'net_assets': str(net) if net is not None else None, 'total_cash': str(cash) if cash is not None else None})
        balances = {'status': '部分完成' if partial else '完整' if rows else '完整但为空', 'reason': 'USD金额缺项' if partial or not rows else '', 'rows': rows}
    except (SafeError, KeyError, TypeError, ValueError):
        pass
    try:
        data = provider.get('/v1/asset/stock')
        if not isinstance(data, dict) or not isinstance(data.get('list'), list):
            raise SafeError('positions_schema')
        rows, partial = [], False
        for channel in data['list']:
            if not isinstance(channel, dict) or not isinstance(channel.get('stock_info'), list):
                partial = True
                continue
            for item in channel['stock_info']:
                if not isinstance(item, dict):
                    partial = True
                    continue
                qty = numeric(item.get('quantity'))
                if qty == 0:
                    continue
                currency = item.get('currency')
                valid_currency = isinstance(currency, str) and re.fullmatch('[A-Z]{3}', currency)
                rows.append({'symbol': str(item.get('symbol') or '身份未提供'), 'name': str(item.get('symbol_name') or ''), 'currency': currency if valid_currency else None, 'quantity': str(qty) if qty is not None else None, 'close_price': None, 'close_date': None, 'close_bar_time': None, 'gap': '收盘价未取得'})
        calendars, prices = {}, {}
        try:
            sessions = provider.call('quote.trading_session') if rows else []
        except (SafeError, ValueError, TypeError):
            sessions = []
        if not isinstance(sessions, list):
            sessions = []
        for row in rows:
            ticker = row['symbol']
            if SYMBOL.fullmatch(ticker) and ticker not in prices:
                try:
                    prices[ticker] = completed_close(provider, ticker, now, calendars, sessions)
                except (SafeError, KeyError, ValueError, TypeError, OverflowError, OSError):
                    prices[ticker] = None
            close = prices.get(ticker)
            if close and row['currency'] and row['quantity'] is not None:
                row.update(close_price=close[0], close_date=close[1], close_bar_time=close[2], gap='')
            else:
                partial = True
        holdings = {'status': '部分完成' if partial else '完整' if rows else '完整但为空', 'reason': '部分持仓或收盘价缺项' if partial else '', 'rows': rows}
    except (SafeError, KeyError, TypeError, ValueError, InvalidOperation):
        pass
    holdings = sort_holdings(provider, holdings)
    return {'as_of': now.isoformat(), 'balances': balances, 'holdings': holdings, 'daily_pnl': collect_daily_pnl(provider, report_day)}


def collect_account(provider, now, ny):
    dates = provider.call("quote.trading_days", {
        "market": "US", "start": (now - timedelta(days=28)).date().isoformat(),
        "end": now.astimezone(ny).date().isoformat(),
    })
    if not isinstance(dates, dict) or not isinstance(dates.get("trading_days"), list):
        raise SafeError("calendar_schema")
    half_days = dates.get("half_trading_days", [])
    if not isinstance(half_days, list):
        raise SafeError("calendar_schema")
    sessions = provider.call("quote.trading_session")
    if not isinstance(sessions, list) or any(not isinstance(item, dict) for item in sessions):
        raise SafeError("session_schema")
    us = next((item for item in sessions if item.get("market") == "US"), None)
    if not us or not isinstance(us.get("trade_sessions"), list):
        raise SafeError("session_missing")
    allowed = [item for item in us["trade_sessions"] if isinstance(item, dict)
               and item.get("trade_session") in {"Pre", "Intraday", "Post"}]
    if not any(item.get("trade_session") == "Post" for item in allowed):
        raise SafeError("session_coverage_missing")
    begin = min(time.fromisoformat(item["begin_time"]) for item in allowed)
    end = max(time.fromisoformat(item["end_time"]) for item in allowed)
    if begin >= end:
        raise SafeError("session_window_invalid")
    completed = []
    for day in set(dates["trading_days"] + half_days):
        date = datetime.fromisoformat(day).date()
        if datetime.combine(date, end, ny).astimezone(UTC) <= now:
            completed.append(date)
    if not completed:
        raise SafeError("completed_day_unavailable")
    day = max(completed)
    start, finish = datetime.combine(day, begin, ny), datetime.combine(day, end, ny)
    trades, seen, complete, reasons = [], set(), False, []
    for page in range(1, 21):
        try:
            data = provider.get("/v3/trade/execution/all", {
                "start_at": str(int(start.timestamp())), "end_at": str(int(finish.timestamp())),
                "page": str(page),
            })
            if not isinstance(data, dict) or not isinstance(data.get("trades"), list):
                raise SafeError("executions_schema")
        except (SafeError, ValueError, TypeError, KeyError):
            reasons.append("成交分页查询未完成")
            break
        before = len(seen)
        for item in data["trades"]:
            if not isinstance(item, dict) or not isinstance(item.get("trade_id"), str):
                reasons.append("部分成交缺少去重标识")
                continue
            key = item["trade_id"]
            if not key:
                reasons.append("部分成交缺少去重标识")
                continue
            if key in seen:
                continue
            seen.add(key)
            try:
                stamp = moment(item["trade_done_at"])
                ticker = symbol(item["symbol"])
                if ticker.endswith(".US") and start.astimezone(UTC) <= stamp <= finish.astimezone(UTC):
                    trades.append(item)
            except (SafeError, KeyError, ValueError, TypeError, OverflowError, OSError):
                reasons.append("部分成交身份或时间无法核对")
        if data.get("has_more") is False:
            complete = True
            break
        if data.get("has_more") is not True or len(seen) == before:
            reasons.append("成交分页状态不完整或重复页")
            break
    else:
        reasons.append("成交分页达到上限")
    tickers = sorted({item["symbol"] for item in trades})
    info, options = {}, {}
    plain = [ticker for ticker in tickers if not OPTION.fullmatch(ticker)]
    if plain:
        try:
            info = mapping(provider.call("quote.static_info", {"symbols": plain}))
        except (SafeError, KeyError, ValueError, TypeError):
            reasons.append("证券名称或币种资料未取得")
    candidates = [ticker for ticker in tickers if OPTION.fullmatch(ticker)
                  or info.get(ticker, {}).get("board") in {"USOption", "USOptionS"}]
    if candidates:
        try:
            options = mapping(provider.call("quote.option_quote", {"symbols": candidates}))
        except (SafeError, KeyError, ValueError, TypeError):
            reasons.append("期权身份或乘数资料未取得")
    rows, order_info = [], {}
    for item in sorted(trades, key=lambda row: moment(row["trade_done_at"])):
        ticker = item["symbol"]
        opt, static = options.get(ticker, {}), info.get(ticker, {})
        side, currency = item.get("side"), static.get("currency")
        if side not in {"Buy", "Sell"} or not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            try:
                order_id = item["order_id"]
                if not isinstance(order_id, str) or not order_id:
                    raise SafeError("order_identity_missing")
                if order_id not in order_info:
                    detail = provider.call("trade.order_detail", {"order_id": order_id})
                    order_info[order_id] = ({"side": detail.get("side"), "currency": detail.get("currency")}
                        if isinstance(detail, dict) and detail.get("symbol") == ticker and detail.get("order_id") == order_id else {})
                supplement = order_info[order_id]
                if side not in {"Buy", "Sell"}:
                    side = supplement.get("side")
                currency = currency or supplement.get("currency")
            except (SafeError, KeyError, ValueError, TypeError):
                pass
        qty, price = number(item.get("quantity")), number(item.get("price"))
        if qty is not None and Decimal(qty) <= 0:
            qty = None
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            currency = None
        multiplier = number(opt.get("contract_multiplier")) if ticker in candidates else "1"
        if multiplier is not None and Decimal(multiplier) <= 0:
            multiplier = None
        amount = str(Decimal(qty) * Decimal(price) * Decimal(multiplier)) if qty and price and multiplier and currency else None
        underlying = ticker
        if ticker in candidates:
            try:
                underlying = symbol(opt["underlying_symbol"])
            except (SafeError, KeyError, ValueError, TypeError):
                underlying = None
                reasons.append("部分期权正股归属未取得")
        if ticker in candidates and (opt.get("direction") not in {"Call", "Put", "C", "P"}
                                    or not opt.get("expiry_date") or number(opt.get("strike_price")) is None):
            reasons.append("部分期权合约身份未完整取得")
        if side not in {"Buy", "Sell"} or amount is None:
            reasons.append("部分方向、币种、量价或乘数未取得")
        rows.append({
            "symbol": ticker, "name": static.get("name_cn") or static.get("name_en") or ticker,
            "underlying": underlying, "instrument": "期权" if ticker in candidates else "正股",
            "direction": opt.get("direction"), "expiry": opt.get("expiry_date"),
            "strike": number(opt.get("strike_price")), "multiplier": multiplier,
            "side": side if side in {"Buy", "Sell"} else "Unknown",
            "time": moment(item["trade_done_at"]).astimezone(ny).isoformat(),
            "quantity": qty, "price": price, "currency": currency, "amount": amount,
        })
    complete = complete and not reasons
    return module(
        "完整" if complete and rows else "完整但为空" if complete else "部分完成",
        "；".join(sorted(set(reasons))), date=day.isoformat(), rows=rows,
        window_start=start.isoformat(), window_end=finish.isoformat(),
        coverage="US 盘前、盘中、盘后；保守按标准盘后结束确认完成，夜盘归属未核验",
    )


def collect_ipo(provider, now, requested=None):
    items, gaps = {}, []
    if requested:
        ticker = symbol(requested)
        if not ticker.endswith(".HK"):
            raise SafeError("ipo_market_not_hk")
        items[ticker] = {"symbol": ticker, "name": ticker, "state": "unknown"}
    else:
        for command in ["subscriptions", "wait-listing"]:
            try:
                raw = provider.command(["ipo", command, "--format", "json"])
                if not isinstance(raw, dict) or not isinstance(raw.get("hk"), list):
                    raise SafeError("ipo_list_schema")
                for item in raw["hk"]:
                    ticker = symbol(item["symbol"])
                    if item.get("state") == "listed":
                        continue
                    items[ticker] = {
                        "symbol": ticker, "name": str(item.get("name") or ticker),
                        "state": str(item.get("state") or "unknown"),
                        "opening_time": item.get("sub_date"),
                        "deadline": item.get("deadline"), "listing_date": item.get("ipo_date"),
                        "currency": item.get("currency"), "issue_price": str(item.get("issue_price") or ""),
                        "entrance_fee": str(item.get("entrance_fee") or ""),
                        "heat": str(item.get("rate_forcast") or ""),
                        "deadline_source": "长桥列表日期；券商可操作截止仍须核验",
                    }
            except (SafeError, ValueError, KeyError, TypeError, AttributeError):
                gaps.append(f"{command} 查询未完成")
    keep = ["name", "industry", "sponsor", "investors", "underwriter", "prospectus",
            "recommend_url", "profile", "rec_purposes", "proceeds_planned",
            "issue_price", "issue_currency", "trade_unit", "ipo_date"]
    for ticker, item in items.items():
        try:
            raw = provider.get("/v1/ipo/profile", {"counter_id": counter(ticker)})
            profile = raw.get("hk") if isinstance(raw, dict) else None
            if not isinstance(profile, dict):
                raise SafeError("ipo_profile_missing")
            item["profile"] = {key: profile[key] for key in keep if key in profile}
            item["profile_time"] = now.isoformat()
            if isinstance(profile.get("name"), str) and profile["name"]:
                item["name"] = profile["name"]
            item["listing_date"] = profile.get("ipo_date") or item.get("listing_date")
        except (SafeError, KeyError, TypeError, ValueError):
            item["gap"] = "发行或业务资料未完整取得"
            gaps.append("部分新股发行资料未完成")
        try:
            timeline = provider.get("/v1/ipo/timeline", {
                "counter_id": counter(ticker), "market": "HK", "flag": "0",
            })
            if not isinstance(timeline, dict) or not isinstance(timeline.get("timeline"), list):
                raise SafeError("ipo_timeline_missing")
            item["timeline"] = [{"name": entry.get("name"), "time": entry.get("time")}
                                for entry in timeline["timeline"] if isinstance(entry, dict)]
        except (SafeError, KeyError, TypeError, ValueError):
            item["gap"] = (item.get("gap", "") + "；新股日程未完整取得").strip("；")
            gaps.append("部分新股日程未完成")
    return module("部分完成" if gaps else "完整" if items else "完整但为空",
                  "；".join(sorted(set(gaps))), rows=list(items.values()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="~/.longbridge-assistant")
    parser.add_argument("--longbridge-bin", default="longbridge")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--ipo-symbol")
    mode.add_argument("--check-connection", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    provider = None
    try:
        ny = ZoneInfo("America/New_York")
        root = private_root(args.output_root)
        if args.ipo_symbol and not symbol(args.ipo_symbol).endswith(".HK"):
            raise SafeError("ipo_market_not_hk")
        now = datetime.now(UTC)
        with lock(root):
            provider = Provider(args.longbridge_bin)
            if args.check_connection:
                end = now.date()
                start = end - timedelta(days=7)
                calendar = provider.call("quote.trading_days", {
                    "market": "US", "start": start.isoformat(), "end": end.isoformat(),
                })
                if not isinstance(calendar, dict):
                    raise SafeError("calendar_schema")
                days = calendar.get("trading_days")
                half_days = calendar.get("half_trading_days", [])
                if not isinstance(days, list) or not isinstance(half_days, list) or not (days + half_days):
                    raise SafeError("calendar_schema")
                for value in days + half_days:
                    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                        raise SafeError("calendar_schema")
                    day = datetime.strptime(value, "%Y-%m-%d").date()
                    if not start <= day <= end:
                        raise SafeError("calendar_schema")
                print(json.dumps({
                    "status": "connected", "cli_version": "0.28.0",
                    "connection_check": "PASS", "probe": "US public trading calendar",
                    "account_capability": "NOT_CHECKED",
                }))
                return 0
            if args.ipo_symbol:
                ipo = collect_ipo(provider, now, args.ipo_symbol)
                public = {
                    "schema": "longbridge-assistant.public.v1", "mode": "ipo_only",
                    "generated_at": now.isoformat(), "ipo": ipo,
                }
                input_path = root / "ipo-input.json"
                write_json(input_path, public)
                status = {"ipo_status": ipo["status"]}
            else:
                account = module(rows=[], date="", coverage="US 成交查询未完成")
                try:
                    account = collect_account(provider, now, ny)
                except (SafeError, ValueError, KeyError, TypeError, InvalidOperation, OverflowError):
                    account["reason"] = "成交或交易日期查询未完成"
                snapshot = collect_snapshot(provider, now, account.get("date"))
                ipo = collect_ipo(provider, now)
                write_json(root / "account.json", {
                    "schema": "longbridge-assistant.account.v1", "generated_at": now.isoformat(),
                    "account": account, "snapshot": snapshot,
                })
                public = {
                    "schema": "longbridge-assistant.public.v1", "mode": "daily",
                    "generated_at": now.isoformat(), "ipo": ipo,
                }
                input_path = root / "analysis-input.json"
                write_json(input_path, public)
                status = {"account_status": account["status"], "balances_status": snapshot["balances"]["status"], "holdings_status": snapshot["holdings"]["status"], "sort_status": snapshot["holdings"]["sort_status"], "daily_pnl_status": snapshot["daily_pnl"]["status"], "ipo_status": ipo["status"]}
        print(json.dumps({
            "status": "collected", "output_root": str(root),
            **status, "analysis_input": str(input_path),
        }, ensure_ascii=False))
    except ZoneInfoNotFoundError:
        status = {"status": "blocked", "reason": "iana_timezone_data_missing"}
        if args.check_connection:
            status.update(connection_check="FAIL", account_capability="NOT_CHECKED")
        print(json.dumps(status))
        return 2
    except (SafeError, OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        reason = "collection_unavailable"
        status = {"status": "blocked"}
        if args.check_connection:
            safe_reasons = {
                "longbridge_missing", "longbridge_binary_unsafe", "cli_version_not_verified",
                "provider_unavailable", "provider_timeout", "provider_protocol",
                "provider_query_failed", "calendar_schema", "run_in_progress",
                "output_inside_git", "output_symlink", "output_not_owned", "runtime_os_not_verified",
            }
            reason = str(exc) if isinstance(exc, SafeError) and str(exc) in safe_reasons else "connection_unavailable"
            status.update(connection_check="FAIL", account_capability="NOT_CHECKED")
        print(json.dumps({**status, "reason": reason}))
        return 2
    finally:
        if provider:
            provider.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
