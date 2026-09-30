"""Render private facts and source-bounded summaries as offline HTML."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
import html
import json
import os
from pathlib import Path
import re
import shutil
from string import Template
import tempfile
from urllib.parse import urlsplit

from private_io import SafeError, load_json, lock, private_root, write_json, write_text

ASSETS = Path(__file__).resolve().parent.parent / "assets"
VERDICTS = {"可以关注", "偏谨慎", "暂时跳过", "资料不足"}


def e(value):
    return html.escape(str(value) if value is not None else "未提供", quote=True)


def safe_url(value):
    try:
        parsed = urlsplit(str(value))
        return str(value) if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password else None
    except ValueError:
        return None


def link(title, url):
    valid = safe_url(url)
    return f'<a href="{e(valid)}" rel="noreferrer noopener">{e(title)}</a>' if valid else e(title) + "（未提供链接）"


def pill(status):
    kind = "good" if status in {"完整", "完整但为空", "可以关注"} else "warn"
    return f'<span class="pill {kind}">{e(status)}</span>'


def money(value, currency=""):
    if value is None:
        return "未提供"
    try:
        decimal = Decimal(str(value))
        if not decimal.is_finite():
            return "未提供"
        return e(currency) + " " + format(decimal.quantize(Decimal(".01")), ",.2f")
    except (InvalidOperation, ValueError):
        return "未提供"


def totals(rows, side):
    result, missing = defaultdict(Decimal), 0
    for row in rows:
        if row["side"] == side:
            if row.get("amount") is None or not row.get("currency"):
                missing += 1
            else:
                result[row["currency"]] += Decimal(row["amount"])
    copy = "<br>".join(money(amount, currency) for currency, amount in sorted(result.items()))
    if missing:
        copy += f'<div class="muted">已知小计，{missing} 笔金额未提供</div>'
    return copy or ("未提供" if missing else "—")


def account_html(data, previous_date):
    rows = data["rows"]
    groups = defaultdict(list)
    for row in rows:
        groups[row.get("underlying") or row["symbol"]].append(row)
    details = ""
    for ticker, items in sorted(groups.items()):
        buys = sum(row["side"] == "Buy" for row in items)
        sells = sum(row["side"] == "Sell" for row in items)
        name = next((row.get("name") for row in items if row["symbol"] == ticker and row.get("name") != ticker), "")
        unknown = sum(row["side"] not in {"Buy", "Sell"} for row in items)
        unknown_copy = f" · {unknown} 笔方向未取得" if unknown else ""
        fills = ""
        for row in items:
            tool = f'{row["instrument"]} · {row["symbol"]}'
            if row["instrument"] == "期权":
                tool += f' · {row.get("direction") or "方向未提供"} · 到期 {row.get("expiry") or "未提供"} · 行权 {row.get("strike") or "未提供"} · 乘数 {row.get("multiplier") or "未提供"}'
            side = {"Buy": "买入", "Sell": "卖出"}.get(row["side"], "方向未提供")
            qty = e(row.get("quantity")) + (" 张" if row["instrument"] == "期权" else " 股")
            fills += (
                f'<tr><td>{e(row["time"])}<br><span class="muted">America/New_York</span></td>'
                f'<td>{e(side)}<br><span class="muted">实际成交回报</span></td><td>{e(tool)}</td><td>{qty}</td>'
                f'<td>{e(row.get("currency") or "币种未提供")} {e(row.get("price"))}</td>'
                f'<td>{money(row.get("amount"), row.get("currency") or "")}</td></tr>'
            )
        details += (
            f'<details class="trade"><summary><div><span class="symbol">{e(ticker)} {e(name)}</span> <span class="meta">{len(items)} 笔成交{e(unknown_copy)}</span></div>'
            f'<div class="small"><span class="buy">买入 {buys} 笔 · {totals(items, "Buy")}</span>　'
            f'<span class="sell">卖出 {sells} 笔 · {totals(items, "Sell")}</span></div><span class="small">展开明细 ↓</span></summary>'
            '<div class="table-wrap"><table><thead><tr><th>成交时间</th><th>方向</th><th>实际工具</th><th>数量</th><th>成交价</th><th>成交额</th></tr></thead>'
            f'<tbody>{fills}</tbody></table></div></details>'
        )
    if not rows:
        details = '<p class="empty">' + ("该完整查询窗口无成交" if data["status"] == "完整但为空" else "成交查询未完成，不能认定无成交") + "</p>"
    complete = data["status"] in {"完整", "完整但为空"}
    count = f"{len(rows)} / {len(groups)}" if complete or rows else "未取得"
    subtotal = "" if complete else "（已取得小计）"
    buy_total = totals(rows, "Buy") if complete or rows else "未取得"
    sell_total = totals(rows, "Sell") if complete or rows else "未取得"
    repeated = " · 与上次相同交易日" if previous_date and data.get("date") == previous_date else ""
    reason = f'<p class="note">{e(data["reason"])}</p>' if data.get("reason") else ""
    return (
        '<section class="panel" id="account"><div class="panel-head"><div><h2>仓位操作简报与成交明细</h2>'
        f'<div class="meta">US · {e(data.get("date") or "交易日未确定")}{e(repeated)}<br>{e(data.get("coverage"))}</div></div>{pill(data["status"])}</div>'
        f'<div class="content">{reason}<div class="stats"><div class="stat"><span class="meta">成交 / 标的{e(subtotal)}</span><strong>{e(count)}</strong></div>'
        f'<div class="stat"><span class="meta">买入成交额{e(subtotal)}</span><strong>{buy_total}</strong></div>'
        f'<div class="stat"><span class="meta">卖出成交额{e(subtotal)}</span><strong>{sell_total}</strong></div></div>'
        f'{details}</div></section>'
    )


def date_value(value):
    try:
        if isinstance(value, (int, float)) or isinstance(value, str) and value.isdigit() and len(value) in {10, 13}:
            stamp = float(value) / (1000 if len(str(value)) == 13 else 1)
            return datetime.fromtimestamp(stamp, timezone.utc)
        text = str(value)
        if re.fullmatch(r"[0-9]{8}", text):
            text = datetime.strptime(text, "%Y%m%d").date().isoformat()
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if result.tzinfo is None:
            if len(text) <= 10:
                return None  # A date alone does not prove a subscription cutoff time.
            result = result.replace(tzinfo=ZoneInfo("Asia/Hong_Kong"))
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def ipo_phase(item, generated_at):
    state, deadline = item.get("state"), date_value(item.get("deadline"))
    now = date_value(generated_at)
    if state in {"cancelled", "delayed"}:
        return 2, "发行取消" if state == "cancelled" else "发行推迟"
    if state == "sub-start":
        if deadline is None:
            return 1, "招股状态待核实 · 截止时间缺失"
        if now and deadline <= now:
            return 2, "已过所示截止 · 可操作状态待核实"
        return 0, "正在招股（以券商实际入口为准）"
    return {"pending": (1, "尚未开始"), "sub-end": (2, "待上市"),
            "allotment": (2, "待上市"), "grey-market": (2, "待上市"),
            "listed": (3, "已上市")}.get(state, (2, "阶段未核实"))


def ipo_order(item, generated_at):
    phase, _ = ipo_phase(item, generated_at)
    value = item.get("opening_time") if item.get("state") == "pending" else item.get("deadline") if phase < 2 else item.get("listing_date")
    parsed = date_value(value)
    if parsed is None and isinstance(value, str):
        try:
            parsed = datetime.combine(datetime.fromisoformat(value[:10]).date(), datetime.min.time(), ZoneInfo("Asia/Hong_Kong"))
        except ValueError:
            pass
    return phase, parsed.timestamp() if parsed else float("inf"), item["symbol"]


def ipo_source_urls(item, judgment):
    profile = item.get("profile", {})
    allowed = {profile[key] for key in ["prospectus", "recommend_url"]
               if isinstance(profile.get(key), str) and safe_url(profile[key])}
    for source in judgment.get("sources", []):
        if not isinstance(source, dict) or source.get("provider") != "Longbridge":
            continue
        url = safe_url(source.get("url"))
        if not url or not isinstance(source.get("title"), str) or not source["title"].strip():
            continue
        parsed = urlsplit(url)
        try:
            port = parsed.port
        except ValueError:
            continue
        if parsed.scheme != "https" or parsed.hostname != "longbridge.com" or port not in {None, 443}:
            continue
        if not re.fullmatch(r"/news/[0-9]+(?:\.md)?", parsed.path) or parsed.query or parsed.fragment:
            continue
        try:
            published = datetime.fromisoformat(str(source.get("time")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if published.tzinfo is not None:
            allowed.add(url)
    return allowed


def ipo_analysis(item, analysis):
    rows = analysis.get("ipo", [])
    result = next((row for row in rows if isinstance(row, dict) and row.get("symbol") == item["symbol"]), {})
    if result.get("conclusion") not in VERDICTS:
        return {"conclusion": "资料不足", "summary": "尚未完成有来源的短线初筛。"}
    if result["conclusion"] == "可以关注":
        urls = ipo_source_urls(item, result)
        evidence_status = result.get("evidence_status", {})
        supported = isinstance(evidence_status, dict) and all(evidence_status.get(key) == "已核对"
                    for key in ["valuation", "competitiveness"])
        sources = result.get("sources", [])
        sourced = isinstance(sources, list) and any(isinstance(row, dict) and row.get("url") in urls for row in sources)
        if not sourced or not supported or any(not isinstance(result.get(key), str) or not result[key].strip()
                                               for key in ["valuation", "competitiveness", "red_flags"]):
            result = {**result, "conclusion": "偏谨慎", "summary": "积极判断的估值或业务支持不足，先保留谨慎初筛；未知项见下文。"}
    return {**result, "analysed_at": analysis.get("analysed_at")}


def ipo_page(item, judgment, generated_at, back="../index.html#ipo"):
    keys = [("valuation", "估值"), ("competitiveness", "竞争力"), ("red_flags", "风险红旗")]
    checks = "".join(f'<section class="check"><h2>{title}</h2><p>{e(judgment.get(key) or "核心资料尚未取得或核对")}</p></section>' for key, title in keys)
    allowed = ipo_source_urls(item, judgment)
    sources = "".join("<li>" + link(source.get("title") or "资料来源", source["url"]) + " · " + e(source.get("time") or "时间见原文") + "</li>"
                      for source in judgment.get("sources", []) if isinstance(source, dict) and source.get("url") in allowed)
    if not sources:
        sources = "".join("<li>" + link("长桥提供的发行资料", url) + "</li>" for url in sorted(allowed))
    gaps = judgment.get("core_gaps", [])
    gaps_text = "；".join(str(value) for value in gaps) if isinstance(gaps, list) else ""
    heat = judgment.get("heat") or ("长桥预计认购参考：" + item["heat"] + "（非全市场最终倍数）" if item.get("heat") else "热度资料未取得")
    return (
        (f'<a href="{e(back)}">← 返回打新提醒</a>' if back else "") +
        f'<h1>{e(item["name"])}</h1><div class="meta">{e(item["symbol"])} · 资料采集时间 {e(item.get("profile_time") or generated_at)} · 分析时间 {e(judgment.get("analysed_at"))}</div>'
        f'<div class="verdict">{pill(judgment["conclusion"])}<p>{e(judgment.get("summary") or "暂无足够依据")}</p></div>'
        f'{checks}<p class="meta">{e(heat)}</p><details class="sources"><summary>来源与资料缺口</summary>'
        f'<ul>{sources or "<li>长桥尚未提供可用原文链接</li>"}</ul><p class="meta">{e("；".join(value for value in [item.get("gap"), gaps_text] if value) or "仅依据已取得公开资料初筛，未做完整财务尽调")}</p>'
        '<p class="meta">资料中的日期与范围请一并核对；申购费、融资利息与交易费用会影响净收益。</p></details>'
    )


def page(title, body, when):
    return Template((ASSETS / "page.html").read_text()).substitute(
        title=e(title), css=(ASSETS / "style.css").read_text(), body=body, time=e(when),
    )


def check_owned(folder):
    if folder.is_symlink():
        raise SafeError("existing_output_not_owned")
    if folder.exists() and (not folder.is_dir() or not (folder / ".manifest.json").is_file()
                            or load_json(folder / ".manifest.json").get("owner") != "longbridge-assistant"):
        raise SafeError("existing_output_not_owned")


def recover_current(root):
    current, backup = root / "current", root / "previous"
    check_owned(current)
    check_owned(backup)
    if not current.exists() and backup.exists():
        backup.rename(current)


def render(root, account, public, analysis):
    if account["generated_at"] != public["generated_at"]:
        raise SafeError("collection_revision_mismatch")
    generated_at = public["generated_at"]
    recover_current(root)
    previous = load_json(root / "state.json") if (root / "state.json").is_file() else {}
    items = sorted([item for item in public["ipo"]["rows"] if item.get("state") != "listed"], key=lambda item: ipo_order(item, generated_at))
    with tempfile.TemporaryDirectory(prefix=".build-", dir=root) as temporary:
        target = Path(temporary)
        os.chmod(target, 0o700)
        ipo_rows = ""
        for item in items:
            ticker = item["symbol"]
            if not re.fullmatch(r"[A-Za-z0-9_-]+\.HK", ticker):
                raise SafeError("ipo_identity_invalid")
            judgment = ipo_analysis(item, analysis)
            filename = ticker + ".html"
            write_text(target / "ipo" / filename, page(item["name"], ipo_page(item, judgment, generated_at), generated_at))
            phase, stage = ipo_phase(item, generated_at)
            deadline = item.get("opening_time") if item.get("state") == "pending" else item.get("deadline") if phase < 2 else item.get("listing_date")
            date_label = "开放时间" if item.get("state") == "pending" else "长桥申购截止" if phase < 2 else "预计上市日期"
            ipo_rows += (
                f'<div class="ipo-row"><div><strong>{e(item["name"])}</strong><div class="meta">{e(ticker)} · {e(stage)}</div>'
                f'<div class="meta">发行价 {e(item.get("currency") or item.get("profile", {}).get("issue_currency") or "币种未提供")} {e(item.get("issue_price") or item.get("profile", {}).get("issue_price") or "未提供")} · 每手入场费 {money(item.get("entrance_fee") or None, item.get("currency") or "")}</div></div>'
                f'<div class="small">{e(date_label)} · {e(deadline or "未提供")}<div class="meta">{e(item.get("deadline_source") or "长桥日程")}</div></div>'
                f'<a class="button" href="ipo/{e(filename)}">{e(judgment["conclusion"])} · 短线评估 →</a></div>'
            )
        ipo = public["ipo"]
        ipo_section = (
            '<section class="panel" id="ipo"><div class="panel-head"><div><h2>港股打新提醒</h2><div class="meta">按阶段与关键日期排列</div></div>'
            f'{pill(ipo["status"])}</div><div class="content">'
            + (f'<p class="note">{e(ipo["reason"])}</p>' if ipo.get("reason") else "")
            + (ipo_rows or '<p class="empty">' + ("暂无可提示新股" if ipo["status"] == "完整但为空" else "新股查询未完成") + "</p>")
            + "</div></section>"
        )
        demo = '<div class="demo">合成演示数据 · 非真实账户或投资结论</div>' if public.get("demo") else ""
        body = demo + '<h1>今日简报</h1><p class="meta">上一完成交易日的仓位操作与港股打新提示</p>'
        body += account_html(account["account"], previous.get("account_date"))
        body += ipo_section
        write_text(target / "index.html", page("今日简报", body, generated_at))
        write_json(target / ".manifest.json", {"owner": "longbridge-assistant", "generated_at": generated_at})
        current, backup = root / "current", root / "previous"
        for folder in [current, backup]:
            check_owned(folder)
        if backup.exists():
            shutil.rmtree(backup)
        moved = current.exists()
        if moved:
            current.rename(backup)
        try:
            target.rename(current)
        except OSError:
            if moved and not current.exists():
                backup.rename(current)
            raise
    account_date = account["account"].get("date") if account["account"]["status"] in {"完整", "完整但为空"} else previous.get("account_date")
    state = {"account_date": account_date, "generated_at": generated_at}
    write_json(root / "state.json", state)
    return root / "current" / "index.html"


def render_single(root, public, analysis):
    items = public["ipo"]["rows"]
    if len(items) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]+\.HK", items[0]["symbol"]):
        raise SafeError("single_ipo_identity_invalid")
    item = items[0]
    folder = root / "ipo-review"
    if folder.is_symlink():
        raise SafeError("output_symlink")
    folder.mkdir(exist_ok=True, mode=0o700)
    back = "../current/index.html#ipo" if (root / "current" / "index.html").is_file() else None
    demo = '<div class="demo">合成演示数据 · 非真实账户或投资结论</div>' if public.get("demo") else ""
    body = demo + ipo_page(item, ipo_analysis(item, analysis), public["generated_at"], back)
    target = folder / (item["symbol"] + ".html")
    write_text(target, page(item["name"], body, public["generated_at"]))
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="~/.longbridge-assistant")
    parser.add_argument("--analysis-file")
    parser.add_argument("--input-file", help="Default: private analysis-input.json; single IPO: ipo-input.json")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        root = private_root(args.output_root)
        with lock(root):
            public = load_json(Path(args.input_file).expanduser()) if args.input_file else load_json(root / "analysis-input.json")
            analysis = load_json(Path(args.analysis_file).expanduser()) if args.analysis_file else {}
            if analysis and analysis.get("collection_generated_at") != public["generated_at"]:
                raise SafeError("analysis_revision_mismatch")
            if analysis:
                stamp = datetime.fromisoformat(str(analysis.get("analysed_at", "")).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise SafeError("analysis_time_missing")
            if public.get("mode") == "ipo_only":
                result = render_single(root, public, analysis)
            else:
                recover_current(root)
                account = load_json(root / "account.json")
                result = render(root, account, public, analysis)
        print(json.dumps({"status": "rendered", "report": str(result)}, ensure_ascii=False))
        return 0
    except (SafeError, OSError, ValueError, KeyError, TypeError, AttributeError, InvalidOperation):
        print('{"status":"blocked","reason":"render_unavailable_previous_report_preserved"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
