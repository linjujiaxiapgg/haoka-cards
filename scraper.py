# -*- coding: utf-8 -*-
"""
号卡数据自动抓取脚本（无需登录、无需服务器）
数据源：号卡宇宙店铺 https://hk.198haoka.cn/index?k=WHFBNWFnV25wVGM9
做法：逐省请求 /GetList，合并去重，得到每张卡真实可发省份
输出：cards.json（供网页自动加载）
"""
import json, re, time, urllib.parse, urllib.request, os

BASE = "https://hk.198haoka.cn"
K = "WHFBNWFnV25wVGM9"
UA = ("Mozilla/5.0 (Linux; Android 13; SM-A5360) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36")

PROVINCES = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海",
             "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
             "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西",
             "甘肃", "青海", "宁夏", "新疆"]

OP_MAP = {"中国移动": "移动", "中国联通": "联通", "中国电信": "电信", "中国广电": "广电"}


def http_get(url, referer=None, ajax=False):
    headers = {"User-Agent": UA, "Referer": referer or url}
    if ajax:
        headers["Accept"] = "application/json, text/plain, */*"
        headers["X-Requested-With"] = "XMLHttpRequest"
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")


def num(v):
    try:
        return int(float(str(v)))
    except Exception:
        return 0


def clean_name(name):
    name = name.strip()
    name = re.sub(r"^[0-9]{2,4}(?=[\u4e00-\u9fa5])", "", name)
    name = re.sub(r"[（(][^）)]*(仅发|只发|全国可发|激活发货|随时下架|部分省份|部分地区|提前下架)[^）)]*[）)]", "", name)
    return name.strip() or name


def fetch_token():
    page = http_get(f"{BASE}/index?k={K}")
    m = re.search(r"(?:var|let|const)\s+i\s*=\s*['\"]([^'\"]+)['\"]", page)
    if not m:
        raise RuntimeError("未能从店铺页提取接口 token")
    return m.group(1)


def fetch_province(token, prov):
    q = urllib.parse.urlencode({"k": K, "i": token, "s": "", "a": f"{prov} {prov}",
                                "y": "", "l": "", "t": "", "c": "", "o": ""})
    for attempt in range(3):
        try:
            raw = http_get(f"{BASE}/GetList?{q}", referer=f"{BASE}/index?k={K}", ajax=True)
            data = json.loads(raw)
            if data.get("code") == 200:
                return data.get("data") or []
        except Exception as e:
            print(f"  {prov} 第{attempt + 1}次失败: {e}")
            time.sleep(1.5)
    return []


def main():
    token = fetch_token()
    cards = {}
    for p in PROVINCES:
        items = fetch_province(token, p)
        print(f"{p}: {len(items)}")
        for it in items:
            name_raw = (it.get("shop_name") or "").strip()
            if "测试" in name_raw or not name_raw:
                continue
            cid = str(it.get("id") or name_raw)
            rec = cards.get(cid)
            if not rec:
                paynum = num(it.get("paynum"))
                provinces_all = []
                rec = {
                    "id": cid,
                    "name": clean_name(name_raw),
                    "rawName": name_raw,
                    "operator": OP_MAP.get((it.get("shop_yys") or "").strip(), (it.get("shop_yys") or "").strip()),
                    "price": num(it.get("monthly_rent")),
                    "general": num(it.get("general_flow")),
                    "direct": num(it.get("directed_flow")),
                    "call": num(it.get("call_minutes")),
                    "ageMin": num(it.get("min_age")) or 18,
                    "ageMax": num(it.get("max_age")) or 60,
                    "tag": (it.get("shop_tag") or "").replace("，", "；"),
                    "paynum": paynum,
                    "provinces": provinces_all,
                }
                cards[cid] = rec
            if p not in rec["provinces"]:
                rec["provinces"].append(p)

    out = []
    for rec in cards.values():
        provs = rec.pop("provinces")
        nationwide = len(provs) >= 30
        rec["province"] = ["全网"] if nationwide else provs
        # 首充：按预存金额
        pay = rec.get("paynum") or 0
        if pay >= 100:
            rec["firstRecharge"] = f"{pay}元"
        elif pay > 0:
            rec["firstRecharge"] = f"{pay}元"
        else:
            rec["firstRecharge"] = "激活时充"
        # 佣金档位（不展示，仅排序用）：分省专属 + 预存高 = 更高佣
        score = 0
        if not nationwide:
            score += 2
        if pay >= 200:
            score += 1
        rec["commissionLevel"] = 3 - min(score, 2)   # 1=最高佣 3=最低佣
        rec.pop("paynum", None)
        rec["channel"] = "号卡宇宙"
        rec["activate"] = "快递员/上门激活"
        rec["note"] = rec.get("tag", "")
        rec["link"] = f"{BASE}/index?k={K}"
        out.append(rec)

    out.sort(key=lambda r: (r["commissionLevel"], r["price"]))
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cards.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"合计 {len(out)} 张卡，已写入 cards.json")


if __name__ == "__main__":
    main()