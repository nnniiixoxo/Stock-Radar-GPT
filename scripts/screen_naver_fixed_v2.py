from __future__ import annotations

import html
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pandas as pd
import requests
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "data" / "results.json"
CHECKPOINT = ROOT / "checkpoint.json"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; StockRadar/1.0)"})


def clean_number(value):
    value = float(value)
    return None if math.isnan(value) or math.isinf(value) else round(value, 4)


def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, np.nan)))


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=12))
def get_text(url):
    response = SESSION.get(url, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "euc-kr"
    return response.text


def fetch_universe():
    universe = []
    # 네이버는 class/href 속성의 순서를 수시로 바꾸므로 class 위치에 의존하지 않는다.
    pattern = re.compile(
        r'<a\b[^>]*href=["\'](?:https://finance\.naver\.com)?/item/main\.naver\?code=(\d{6})["\'][^>]*>(.*?)</a>',
        re.I | re.S,
    )
    for market, sosok in (("KOSPI", 0), ("KOSDAQ", 1)):
        seen, empty_pages = set(), 0
        for page in range(1, 81):
            text = get_text(
                f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
            )
            added = 0
            for code, raw_name in pattern.findall(text):
                name = re.sub(r"<[^>]+>", "", raw_name).strip()
                if not name:
                    continue
                if code not in seen:
                    seen.add(code)
                    universe.append((code, html.unescape(name), market))
                    added += 1
            empty_pages = empty_pages + 1 if added == 0 else 0
            if empty_pages >= 2:
                break
            time.sleep(0.12)
    if len(universe) < 1500:
        raise RuntimeError(f"상장종목 목록이 비정상적으로 적습니다: {len(universe)}개")
    return universe


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=12))
def fetch_prices(code, count=130):
    url = (
        "https://fchart.stock.naver.com/sise.nhn"
        f"?symbol={code}&timeframe=day&count={count}&requestType=0"
    )
    response = SESSION.get(url, timeout=20)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    rows = []
    for item in root.findall(".//item"):
        values = (item.attrib.get("data") or "").split("|")
        if len(values) >= 6:
            rows.append(values[:6])
    if len(rows) < 65:
        raise ValueError(f"일봉 부족: {len(rows)}")
    frame = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    for column in ("close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["close", "volume"])
    frame["value"] = frame["close"] * frame["volume"]
    return frame


def analyze(code, name, market, cfg):
    try:
        frame = fetch_prices(code)
        close = frame.close.astype(float)
        volume = frame.volume.astype(float)
        value = frame.value.astype(float)
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        relative_volume = volume / volume.rolling(20).mean()
        rs = rsi(close)
        disparity = close / ma20 * 100
        points = cfg["scoring"]
        matched = []

        def hit(ok, key, label):
            if bool(ok):
                matched.append({"key": key, "label": label, "points": points[key]})

        hit(ma5.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1], "ma_alignment", "정배열")
        hit(ma20.iloc[-1] > ma20.iloc[-3], "ma20_rising", "MA20 상승")
        hit(ma60.iloc[-1] > ma60.iloc[-3], "ma60_rising", "MA60 상승")
        hit(35 <= rs.iloc[-1] <= 50, "rsi_35_50", "RSI 35~50")
        hit(rs.iloc[-1] > rs.iloc[-2] <= rs.iloc[-3], "rsi_turn_up", "RSI 상승전환")
        hit(disparity.iloc[-1] > disparity.iloc[-2] <= disparity.iloc[-3], "disparity_rebound", "이격도 반등")
        hit(relative_volume.iloc[-1] >= 2, "rvol_2x", "RVOL≥2")
        hit(value.iloc[-1] > value.iloc[-2], "trading_value_increase", "거래대금 증가")
        change = (close.iloc[-1] / close.iloc[-2] - 1) * 100
        return {
            "code": code,
            "name": name,
            "market": market,
            "score": sum(item["points"] for item in matched),
            "matched": matched,
            "close": clean_number(close.iloc[-1]),
            "change_pct": clean_number(change),
            "rsi": clean_number(rs.iloc[-1]),
            "rvol": clean_number(relative_volume.iloc[-1]),
            "data_date": str(frame.date.iloc[-1]),
        }
    except Exception as exc:
        return {"code": code, "name": name, "market": market, "error": str(exc)[:160]}


def main():
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    universe = fetch_universe()
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=cfg.get("workers", 5)) as pool:
        futures = {pool.submit(analyze, *item, cfg): item for item in universe}
        for index, future in enumerate(as_completed(futures), 1):
            row = future.result()
            (errors if "error" in row else results).append(row)
            if index % 100 == 0:
                CHECKPOINT.write_text(
                    json.dumps({"completed": index, "total": len(universe), "at": datetime.now().isoformat()}),
                    encoding="utf-8",
                )
    if len(results) < len(universe) * 0.75:
        raise RuntimeError(f"시세 수집 성공률 부족: {len(results)}/{len(universe)}")
    results.sort(key=lambda row: (-row["score"], -(row.get("change_pct") or -999)))
    dates = [row.get("data_date") for row in results if row.get("data_date")]
    payload = {
        "status": "ok" if len(results) >= len(universe) * 0.9 else "partial",
        "generated_at": datetime.now().astimezone().isoformat(),
        "base_date": max(dates) if dates else None,
        "scanned_count": len(universe),
        "successful_count": len(results),
        "error_count": len(errors),
        "stocks": results,
        "errors": errors[:50],
    }
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(OUT)
    if CHECKPOINT.exists():
        CHECKPOINT.unlink()
    keys = ("status", "scanned_count", "successful_count", "error_count")
    print(json.dumps({key: payload[key] for key in keys}, ensure_ascii=False))


if __name__ == "__main__":
    main()
