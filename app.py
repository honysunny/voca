"""
영어 암기장 - 단어 / 숙어 / 구동사 암기 & 복습 앱 (Streamlit)
실행: streamlit run app.py
"""
import html
import json
import re
import random
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

# ───────────────────────── 설정 ─────────────────────────
DB_PATH = "vocab.db"
KINDS = ["단어", "숙어", "구동사", "표현"]
# 단계(box)별 다음 복습까지 간격(일) - 라이트너 방식 간격 반복
INTERVALS = [0, 1, 2, 4, 7, 15, 30]
MAX_BOX = len(INTERVALS) - 1
MASTERED_BOX = 5
KST = ZoneInfo("Asia/Seoul")

PAGES = ["🏠 홈", "🃏 복습", "➕ 추가", "📝 퀴즈", "📋 목록"]

# 경험치(XP) 규칙
XP = {"good": 10, "hard": 5, "again": 2, "quiz_ok": 5, "quiz_ng": 1}
XP_PER_LEVEL = 500

# 하늘색 테마
SKY, SKY_D, SKY_L, SKY_M = "#2B9FE6", "#0B5E91", "#E4F4FD", "#9BD3F5"
INK, MUTED, LINE = "#1B2B38", "#6B7F8E", "#D9EAF5"

st.set_page_config(page_title="영어 암기장", page_icon="📚", layout="centered")

st.markdown(
    f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
    .stApp, .stApp button, .stApp input, .stApp textarea {{
        font-family: 'Pretendard', -apple-system, 'Apple SD Gothic Neo', sans-serif !important;
    }}
    #MainMenu, footer {{visibility: hidden;}}
    header[data-testid="stHeader"], [data-testid="stToolbar"] {{display: none;}}
    .block-container {{padding-top: 3.6rem; padding-bottom: 5rem; max-width: 560px;}}
    h2, h3 {{letter-spacing: -0.02em; color: {INK};}}

    /* 버튼 */
    .stButton button, .stDownloadButton button {{
        min-height: 3.1rem; font-size: 1.02rem; font-weight: 600;
        border-radius: 14px; border: 1.5px solid {LINE}; background: #fff; color: {INK};
    }}
    button[kind="primary"], [data-testid="stBaseButton-primary"] {{
        background: {SKY} !important; border-color: {SKY} !important; color: #fff !important;
    }}
    button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {{background: #1E8AD0 !important;}}

    /* 상단 탭바 */
    .st-key-nav {{
        position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
        background: rgba(255,255,255,.96); border-bottom: 1px solid {LINE}; padding: 6px 6px 0;
    }}
    .st-key-nav > div, .st-key-nav [data-testid="stElementContainer"], .st-key-nav [data-testid="stRadio"] {{
        width: 100% !important;
    }}
    .st-key-nav [role="radiogroup"] {{
        display: flex; flex-wrap: nowrap; justify-content: space-between; gap: 0;
        width: 100%; max-width: 560px; margin: 0 auto;
    }}
    /* 각 메뉴 칸 (신버전: div > label[stRadioOption], 구버전: label[data-baseweb]) */
    .st-key-nav [role="radiogroup"] > div, .st-key-nav label[data-baseweb="radio"] {{
        flex: 1 1 0; display: flex; justify-content: center; margin: 0;
        padding: 8px 0 10px; border-bottom: 3px solid transparent;
    }}
    .st-key-nav [role="radiogroup"] > div[data-selected="true"],
    .st-key-nav label[data-baseweb="radio"]:has(input:checked) {{border-bottom-color: {SKY};}}
    .st-key-nav [data-testid="stRadioOption"], .st-key-nav [data-testid="stRadioOption"] > div {{
        width: 100%; justify-content: center; text-align: center;
    }}
    /* 라디오 동그라미 숨기기 */
    .st-key-nav [data-testid="stRadioOption"] > div > div:first-child:not([data-testid]),
    .st-key-nav label[data-baseweb="radio"] > div:first-child {{display: none !important;}}
    .st-key-nav [role="radiogroup"] p {{font-size: 14px; font-weight: 600; color: {MUTED}; white-space: nowrap; margin: 0;}}
    .st-key-nav [data-selected="true"] p, .st-key-nav label:has(input:checked) p {{color: {SKY_D};}}

    /* 복습 평가 버튼 한 줄로 */
    .st-key-grade [data-testid="stHorizontalBlock"] {{flex-wrap: nowrap !important; gap: 8px;}}
    .st-key-grade [data-testid="stColumn"] {{min-width: 0 !important; width: auto !important; flex: 1 1 0 !important;}}
    .st-key-again button {{background: #FDECEC !important; color: #9B2C2C !important; border: none !important;}}
    .st-key-hard button {{background: #FFF3DC !important; color: #8A5A0B !important; border: none !important;}}
    .st-key-good button {{background: {SKY} !important; color: #fff !important; border: none !important;}}

    /* 퀴즈 보기 */
    .st-key-opts .stButton button {{justify-content: flex-start; text-align: left; padding: 0 18px;}}
    </style>
    """,
    unsafe_allow_html=True,
)


# ───────────────────────── DB ─────────────────────────
@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS cards(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            example TEXT DEFAULT '',
            note TEXT DEFAULT '',
            box INTEGER DEFAULT 0,
            due TEXT NOT NULL,
            correct INTEGER DEFAULT 0,
            wrong INTEGER DEFAULT 0,
            created TEXT NOT NULL,
            last_reviewed TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS stats(
            day TEXT PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            reviews INTEGER DEFAULT 0
        )"""
    )
    conn.commit()
    return conn


def add_xp(xp, reviews=1):
    conn = get_conn()
    conn.execute(
        """INSERT INTO stats(day, xp, reviews) VALUES(?,?,?)
           ON CONFLICT(day) DO UPDATE SET xp = xp + excluded.xp, reviews = reviews + excluded.reviews""",
        (today().isoformat(), xp, reviews),
    )
    conn.commit()


def get_stats():
    rows = get_conn().execute("SELECT day, xp, reviews FROM stats").fetchall()
    total = sum(r["xp"] for r in rows)
    days = {r["day"] for r in rows if r["reviews"] > 0}
    t = today()
    d = t if t.isoformat() in days else t - timedelta(days=1)  # 오늘 아직 안 했어도 어제까지 이어졌으면 유지
    streak = 0
    while d.isoformat() in days:
        streak += 1
        d -= timedelta(days=1)
    td = next((r for r in rows if r["day"] == t.isoformat()), None)
    return {
        "total": total,
        "level": total // XP_PER_LEVEL + 1,
        "in_level": total % XP_PER_LEVEL,
        "streak": streak,
        "done_today": t.isoformat() in days,
        "today_xp": td["xp"] if td else 0,
        "today_reviews": td["reviews"] if td else 0,
    }


def now():
    return datetime.now(KST)


def today():
    return now().date()


def add_card(kind, front, back, example="", note="", box=0, due=None):
    front, back = str(front).strip(), str(back).strip()
    if not front or not back:
        return False, "영어와 뜻을 모두 입력해줘."
    if kind not in KINDS:
        kind = "단어"
    conn = get_conn()
    dup = conn.execute(
        "SELECT id FROM cards WHERE lower(front)=lower(?) AND kind=?", (front, kind)
    ).fetchone()
    if dup:
        return False, f"이미 있음: {front}"
    conn.execute(
        "INSERT INTO cards(kind,front,back,example,note,box,due,created) VALUES(?,?,?,?,?,?,?,?)",
        (
            kind, front, back, str(example or "").strip(), str(note or "").strip(),
            int(box), due or today().isoformat(), now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    return True, f"추가됨: {front}"


def load_df():
    return pd.read_sql_query("SELECT * FROM cards ORDER BY id DESC", get_conn())


def get_card(cid):
    return get_conn().execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()


def card_ids(kinds, only_due):
    if not kinds:
        return []
    ph = ",".join("?" * len(kinds))
    sql = f"SELECT id FROM cards WHERE kind IN ({ph})"
    params = list(kinds)
    if only_due:
        sql += " AND due<=?"
        params.append(today().isoformat())
    return [r["id"] for r in get_conn().execute(sql, params).fetchall()]


def grade(cid, result):
    """result: again(몰라요) / hard(헷갈려요) / good(알아요)"""
    c = get_card(cid)
    if c is None:
        return
    box, t = c["box"], today()
    correct, wrong = c["correct"], c["wrong"]
    if result == "again":
        box, due, wrong = 0, t, wrong + 1
    elif result == "hard":
        due, correct = t + timedelta(days=max(1, INTERVALS[box] // 2)), correct + 1
    else:
        box = min(box + 1, MAX_BOX)
        due, correct = t + timedelta(days=INTERVALS[box]), correct + 1
    conn = get_conn()
    conn.execute(
        "UPDATE cards SET box=?, due=?, correct=?, wrong=?, last_reviewed=? WHERE id=?",
        (box, due.isoformat(), correct, wrong, now().isoformat(timespec="seconds"), cid),
    )
    conn.commit()


# ───────────────────────── UI 헬퍼 ─────────────────────────
def esc(s):
    return html.escape(str(s or ""))


def show(h):
    st.markdown(h, unsafe_allow_html=True)


def pill(text, bg=SKY_L, fg=SKY_D):
    return (f'<span style="background:{bg};color:{fg};font-size:12px;font-weight:600;'
            f'padding:4px 10px;border-radius:999px;">{esc(text)}</span>')


def card_html(main, sub=""):
    sub_html = f'<div style="margin-bottom:14px">{pill(sub)}</div>' if sub else ""
    return f"""
    <div style="background:#fff;border:2px solid {SKY_M};border-radius:22px;padding:30px 18px;
                text-align:center;margin:6px 0 12px;">
      {sub_html}
      <div style="font-size:1.9rem;font-weight:700;line-height:1.3;color:{INK};word-break:break-word;">
        {esc(main)}
      </div>
    </div>"""


def progress_html(ratio, right_text, color=SKY):
    pct = max(0, min(100, round(ratio * 100)))
    return f"""
    <div style="display:flex;align-items:center;gap:10px;margin:4px 0 10px;">
      <div style="flex:1;height:12px;background:{SKY_L};border-radius:999px;overflow:hidden;">
        <div style="width:{pct}%;height:100%;background:{color};border-radius:999px;"></div>
      </div>
      <span style="font-size:13px;font-weight:600;color:{MUTED};white-space:nowrap;">{esc(right_text)}</span>
    </div>"""


def answer_html(answer, example="", note=""):
    ex = "".join(f'<div style="margin-top:6px;font-size:15px;color:#0F5A44;">{esc(l)}</div>'
                 for l in (example or "").splitlines() if l.strip())
    nt = "".join(f'<div style="font-size:13px;color:{MUTED};margin-top:4px;">{esc(l)}</div>'
                 for l in (note or "").splitlines() if l.strip())
    nt = f'<div style="border-top:1px solid #CDEBDF;margin-top:10px;padding-top:8px;">{nt}</div>' if nt else ""
    return f"""
    <div style="background:#E6F6EF;border-radius:18px;padding:16px 18px;margin:0 0 12px;">
      <div style="font-size:1.25rem;font-weight:700;color:#0B4A38;">{esc(answer)}</div>{ex}{nt}
    </div>"""


def tile(label, value, bg=SKY_L, fg=SKY_D):
    return (f'<div style="background:{bg};border-radius:16px;padding:14px 16px;">'
            f'<div style="font-size:13px;color:{fg};opacity:.8;">{esc(label)}</div>'
            f'<div style="font-size:22px;font-weight:700;color:{fg};">{esc(value)}</div></div>')


def _iframe(src, height):
    # 최신 버전은 st.iframe, 구버전은 components.html
    if hasattr(st, "iframe"):
        st.iframe(src, height=height)
    else:
        components.html(src, height=height)


def speak_button(text):
    """브라우저 내장 TTS로 발음 듣기"""
    t = json.dumps(str(text)).replace("</", "<\\/")
    _iframe(
        f"""
        <style>body{{margin:0}}</style>
        <button id="b" style="width:100%;padding:10px;border-radius:14px;border:none;
               background:{SKY_L};font-size:15px;font-weight:600;cursor:pointer;color:{SKY_D};
               font-family:-apple-system,'Apple SD Gothic Neo',sans-serif;">🔊 발음 듣기</button>
        <script>
          document.getElementById('b').onclick = () => {{
            const u = new SpeechSynthesisUtterance({t});
            u.lang = 'en-US'; u.rate = 0.9;
            speechSynthesis.cancel(); speechSynthesis.speak(u);
          }};
        </script>""",
        52,
    )


def go_to(page):
    st.session_state.page = page


# ───────────────────────── 페이지: 홈 ─────────────────────────
def page_home():
    df = load_df()
    s = get_stats()

    fire = "🔥"
    show(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <div style="font-size:24px;font-weight:800;color:{INK};letter-spacing:-0.03em;">영어 암기장</div>
      {pill(f"{fire} {s['streak']}일 연속", "#FFEDE6", "#9A3412")}
    </div>
    <div style="display:flex;justify-content:space-between;font-size:13px;font-weight:600;color:{MUTED};">
      <span>Lv. {s['level']}</span><span>{s['in_level']} / {XP_PER_LEVEL} XP</span>
    </div>""")
    show(progress_html(s["in_level"] / XP_PER_LEVEL, f"오늘 +{s['today_xp']}"))

    if df.empty:
        show(f"""
        <div style="background:{SKY};border-radius:22px;padding:22px 20px;color:#fff;margin:6px 0 10px;">
          <div style="font-size:14px;opacity:.85;">시작해볼까?</div>
          <div style="font-size:26px;font-weight:800;margin-top:2px;">첫 단어를 넣어봐</div>
        </div>""")
        st.button("단어 추가하기", type="primary", on_click=go_to, args=("➕ 추가",), width="stretch")
        return

    t = today().isoformat()
    due = int((df["due"] <= t).sum())
    mastered = int((df["box"] >= MASTERED_BOX).sum())

    if due:
        title, sub = f"{due}개 남았어", "오늘의 복습"
    else:
        title, sub = "오늘 복습 끝! 👏", "잘했어"
    show(f"""
    <div style="background:{SKY};border-radius:22px;padding:22px 20px;color:#fff;margin:6px 0 10px;">
      <div style="font-size:14px;opacity:.85;">{sub}</div>
      <div style="font-size:28px;font-weight:800;margin-top:2px;">{title}</div>
    </div>""")
    if due:
        st.button("복습 시작하기", type="primary", on_click=go_to, args=("🃏 복습",), width="stretch")
    else:
        st.button("퀴즈로 한 번 더 다지기", on_click=go_to, args=("📝 퀴즈",), width="stretch")

    show(f"""
    <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:8px 0 14px;">
      {tile("오늘 복습한 것", f"{s['today_reviews']}개")}
      {tile("암기 완료", f"{mastered}개", "#E6F6EF", "#0B4A38")}
      {tile("전체 카드", f"{len(df)}개", "#F1F4F7", INK)}
      {tile("총 경험치", f"{s['total']} XP", "#FFF3DC", "#7A4A06")}
    </div>""")

    counts = df["kind"].value_counts()
    show('<div style="display:flex;flex-wrap:wrap;gap:6px;">'
         + "".join(pill(f"{k} {counts.get(k, 0)}", "#F1F4F7", MUTED) for k in KINDS) + "</div>")


# ───────────────────────── 자동 완성 ─────────────────────────
AI_MODEL = "claude-haiku-5-5"
PARTICLES = {"up", "down", "off", "out", "in", "on", "away", "back", "over",
             "through", "around", "about", "along", "across", "into", "after", "by"}

AI_PROMPT = """너는 한국인 영어 학습자를 위한 단어장 도우미야.
아래 영어 항목 각각에 대해 JSON 배열만 출력해. 설명이나 코드블록 없이 JSON만.
각 원소 형식:
{"front": 원문 그대로, "kind": "단어"|"숙어"|"구동사"|"표현" 중 하나,
 "back": 자주 쓰는 한국어 뜻을 자주 쓰는 순서로 최대 4개, 쉼표로 구분,
 "example": 뜻마다 예문 하나씩, 뜻 순서대로 한 줄에 하나씩. 각 줄은 "1) 영어 예문 (한국어 해석)" 형식}
항목:
"""


def get_api_key():
    try:
        return st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        return ""


def guess_kind(word):
    w = word.lower().split()
    if len(w) == 1:
        return "단어"
    if len(w) <= 3 and any(p in PARTICLES for p in w[1:]):
        return "구동사"
    return "숙어"


def _parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


@st.cache_data(ttl=86400, show_spinner=False)
def ai_fill(words):
    import anthropic

    client = anthropic.Anthropic(api_key=get_api_key())
    msg = client.messages.create(
        model=AI_MODEL,
        max_tokens=300 + 200 * len(words),
        messages=[{"role": "user", "content": AI_PROMPT + "\n".join(f"- {w}" for w in words)}],
    )
    data = _parse_json("".join(b.text for b in msg.content if b.type == "text"))
    by_word = {str(d.get("front", "")).strip().lower(): d for d in data}
    return [by_word.get(w.lower()) or (data[i] if i < len(data) else {}) for i, w in enumerate(words)]


MYMEMORY_URL = "https://api.mymemory.translated.net/get"
DICT_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
WIKI_URL = "https://en.wiktionary.org/api/rest_v1/page/definition/"
UA = {"User-Agent": "vocab-app/1.0 (personal study app)"}
HANGUL = re.compile("[가-힣]")
TAG = re.compile(r"<[^>]+>")
POS_KO = {"noun": "명", "verb": "동", "adjective": "형", "adverb": "부", "preposition": "전",
          "phrase": "구", "idiom": "관용", "prepositional phrase": "전치사구", "interjection": "감"}
MAX_SENSES = 4


def _clean(s):
    return html.unescape(TAG.sub("", s or "")).strip()


def _ko_meanings(word):
    """MyMemory 번역 결과 + 번역 메모리 후보들에서 한국어 뜻 여러 개 모으기"""
    out = []
    try:
        j = requests.get(MYMEMORY_URL, params={"q": word, "langpair": "en|ko"}, timeout=8).json()
        cands = [j.get("responseData", {}).get("translatedText", "")]
        matches = sorted(j.get("matches") or [], key=lambda m: -float(m.get("match") or 0))
        cands += [m.get("translation", "") for m in matches
                  if str(m.get("segment", "")).strip().lower() == word.lower()]
        for c in cands:
            for part in re.split(r"[,;/·]", str(c)):
                p = part.strip().strip(".")
                if p and HANGUL.search(p) and len(p) <= 20 and p not in out:
                    out.append(p)
    except Exception:
        pass
    return out[:MAX_SENSES]


def _en_senses(word):
    """[(품사, 영영 뜻, 예문)] — 예문 있는 뜻 우선. 구동사·숙어는 위키낱말사전으로 보충"""
    senses = []
    try:
        r = requests.get(DICT_URL + quote(word), timeout=8)
        if r.ok:
            for e in r.json():
                for m in e.get("meanings", []):
                    for d in m.get("definitions", []):
                        senses.append((m.get("partOfSpeech", ""), d.get("definition", ""), d.get("example", "")))
    except Exception:
        pass
    if not any(s[2] for s in senses):
        try:
            r = requests.get(WIKI_URL + quote(word.replace(" ", "_")), headers=UA, timeout=8)
            if r.ok:
                for e in r.json().get("en", []):
                    for d in e.get("definitions", []):
                        exs = [x.get("example", "") for x in d.get("parsedExamples") or []] or d.get("examples") or []
                        senses.append((e.get("partOfSpeech", "").lower(), _clean(d.get("definition")),
                                       _clean(exs[0]) if exs else ""))
        except Exception:
            pass
    senses = [s for s in senses if s[1]]
    return [s for s in senses if s[2]] + [s for s in senses if not s[2]]


@st.cache_data(ttl=86400, show_spinner=False)
def free_fill(word):
    """키 없이: 한국어 뜻은 MyMemory, 영영 뜻·예문은 Free Dictionary / Wiktionary"""
    meanings = _ko_meanings(word)
    senses = _en_senses(word)[:max(2, min(MAX_SENSES, len(meanings)))]
    examples = [ex for _, _, ex in senses if ex]
    return {
        "front": word,
        "kind": guess_kind(word),
        "back": ", ".join(meanings),
        "example": "\n".join(f"{i}) {ex}" for i, ex in enumerate(examples, 1)),
        "note": "\n".join(f"({POS_KO.get(p, p)}) {d}" if p else d for p, d, _ in senses),
    }


def autofill(words):
    """(결과 리스트, 사용한 방식) 반환. AI 실패 시 무료 사전으로 대체"""
    words = [w.strip() for w in words if w.strip()]
    if get_api_key():
        try:
            out = []
            for i in range(0, len(words), 20):
                out += ai_fill(tuple(words[i:i + 20]))
            return out, "AI"
        except Exception as e:
            st.session_state.ai_error = f"AI 호출 실패 → 무료 사전으로 대체 ({e.__class__.__name__})"
    return [free_fill(w) for w in words], "무료 사전"


# ───────────────────────── 페이지: 추가 ─────────────────────────
def _autofill_one():
    ss = st.session_state
    word = ss.a_front.strip()
    if not word:
        ss.a_msg = ("warning", "영어를 먼저 입력해줘.")
        return
    (r,), src = autofill([word])
    ss.a_back = r.get("back", "")
    ss.a_example = r.get("example", "")
    ss.a_note = r.get("note", "")
    if r.get("kind") in KINDS:
        ss.a_kind = r["kind"]
    if r.get("back") or r.get("example"):
        ss.a_msg = ("info", f"✨ {src}로 채웠어. 확인하고 고쳐서 추가해.")
    else:
        ss.a_msg = ("warning", "자동 완성 결과가 없어. 직접 입력해줘.")


def _add_one():
    ss = st.session_state
    ok, msg = add_card(ss.a_kind, ss.a_front, ss.a_back, ss.a_example, ss.a_note)
    ss.a_msg = ("success" if ok else "warning", msg)
    if ok:
        for k in ["a_front", "a_back", "a_example", "a_note"]:
            ss[k] = ""


def page_add():
    ss = st.session_state
    for k in ["a_front", "a_back", "a_example", "a_note"]:
        ss.setdefault(k, "")
    ss.setdefault("a_kind", KINDS[0])

    st.subheader("카드 추가")
    if get_api_key():
        st.caption("✨ 자동 완성: Claude AI")
    else:
        st.caption("✨ 자동 완성: 무료 사전 (구동사·숙어는 부정확할 수 있어. AI 키를 넣으면 훨씬 좋아져)")
    if ss.get("ai_error"):
        st.warning(ss.pop("ai_error"))

    tab1, tab2 = st.tabs(["하나씩", "여러 개 한번에"])

    with tab1:
        st.text_input("영어", key="a_front", placeholder="e.g. look forward to")
        st.button("✨ 뜻·예문 자동 완성", on_click=_autofill_one, width="stretch")
        if ss.get("a_msg"):
            level, text = ss.pop("a_msg")
            getattr(st, level)(text)
        st.selectbox("종류", KINDS, key="a_kind")
        st.text_input("뜻", key="a_back", placeholder="e.g. ~을 고대하다")
        st.text_area("예문 (선택)", key="a_example", height=110)
        st.text_area("메모 (선택)", key="a_note", height=80, placeholder="영영 뜻, 유의어, 헷갈리는 점 등")
        st.button("추가", type="primary", on_click=_add_one, width="stretch")

    with tab2:
        st.caption("한 줄에 하나씩. 영어만 써도 되고, `영어 | 뜻 | 예문`처럼 직접 써도 돼 (엑셀 복붙도 가능)")
        kind_opt = st.selectbox("종류", ["자동"] + KINDS, key="bulk_kind")
        fill = st.checkbox("비어 있는 뜻·예문 자동 채우기", value=True)
        text = st.text_area("목록", height=200,
                            placeholder="give up\nrun out of\nin terms of | ~의 관점에서")
        if st.button("한번에 추가", type="primary", width="stretch"):
            rows = []
            for line in text.splitlines():
                if not line.strip():
                    continue
                parts = [p.strip() for p in (line.split("\t") if "\t" in line else line.split("|"))]
                parts += [""] * (3 - len(parts))
                rows.append(parts[:3])

            info = {}
            need = [r[0] for r in rows if not r[1] or not r[2]]
            if fill and need:
                with st.spinner(f"{len(need)}개 자동 완성 중..."):
                    results, src = autofill(need)
                info = {w.lower(): r for w, r in zip(need, results)}
                if ss.get("ai_error"):
                    st.warning(ss.pop("ai_error"))

            added, skipped = 0, []
            for front, back, ex in rows:
                r = info.get(front.lower(), {})
                back = back or r.get("back", "")
                ex = ex or r.get("example", "")
                kind = kind_opt if kind_opt != "자동" else (r.get("kind") if r.get("kind") in KINDS else guess_kind(front))
                if not back:
                    skipped.append(f"{front} (뜻 없음)")
                    continue
                ok, msg = add_card(kind, front, back, ex, r.get("note", ""))
                added += ok
                if not ok:
                    skipped.append(msg)
            st.success(f"{added}개 추가됨 · 📋 목록에서 확인/수정할 수 있어")
            if skipped:
                with st.expander(f"건너뜀 {len(skipped)}개"):
                    st.write("\n".join(f"- {s}" for s in skipped))


# ───────────────────────── 페이지: 복습(플래시카드) ─────────────────────────
def _rv_show():
    st.session_state.rv_show = True


def _rv_answer(result):
    ss = st.session_state
    cid = ss.rv_queue.pop(0)
    grade(cid, result)
    add_xp(XP[result])
    ss.rv_xp = ss.get("rv_xp", 0) + XP[result]
    if result == "again":
        ss.rv_queue.append(cid)  # 모르면 이번 세션 끝에 다시 나옴
    else:
        ss.rv_done += 1
    ss.rv_show = False
    if not ss.rv_queue:
        ss.rv_msg = f"🎉 {ss.rv_total}개 복습 완료! +{ss.rv_xp} XP"


def _rv_stop():
    ss = st.session_state
    ss.rv_queue = []
    ss.rv_msg = f"{ss.rv_done}/{ss.rv_total}개 하고 멈췄어. +{ss.get('rv_xp', 0)} XP"


def page_review():
    ss = st.session_state
    ss.setdefault("rv_queue", [])

    if not ss.rv_queue:
        st.subheader("플래시카드 복습")
        if ss.get("rv_msg"):
            st.success(ss.pop("rv_msg"))
        kinds = st.multiselect("종류", KINDS, default=KINDS)
        direction = st.radio("방향", ["영어 → 뜻", "뜻 → 영어"], horizontal=True)
        scope = st.radio("범위", ["오늘 복습할 것", "전체에서 랜덤"], horizontal=True)
        limit = st.slider("최대 장수", 5, 100, 20, 5)
        n_due = len(card_ids(kinds, True))
        st.caption(f"오늘 복습 대상: {n_due}개")
        if st.button("시작", type="primary", width="stretch", disabled=not kinds):
            ids = card_ids(kinds, scope == "오늘 복습할 것")
            random.shuffle(ids)
            ids = ids[:limit]
            if not ids:
                st.info("복습할 카드가 없어. 범위를 '전체에서 랜덤'으로 바꿔봐.")
            else:
                ss.update(rv_queue=ids, rv_dir=direction, rv_show=False, rv_done=0,
                          rv_total=len(ids), rv_xp=0)
                st.rerun()
        return

    c = get_card(ss.rv_queue[0])
    if c is None:
        ss.rv_queue.pop(0)
        st.rerun()

    show(progress_html(ss.rv_done / ss.rv_total, f"{ss.rv_done}/{ss.rv_total}"))
    en_first = ss.rv_dir == "영어 → 뜻"
    question = c["front"] if en_first else c["back"]
    show(card_html(question, f"{c['kind']} · {c['box']}단계"))
    if en_first:
        speak_button(c["front"])

    if not ss.rv_show:
        st.button("정답 보기", type="primary", on_click=_rv_show, width="stretch")
    else:
        answer = c["back"] if en_first else c["front"]
        show(answer_html(answer, c["example"], c["note"]))
        if not en_first:
            speak_button(c["front"])
        with st.container(key="grade"):
            b1, b2, b3 = st.columns(3)
            b1.button("😵 몰라요", key="again", on_click=_rv_answer, args=("again",), width="stretch")
            b2.button("🤔 헷갈려", key="hard", on_click=_rv_answer, args=("hard",), width="stretch")
            b3.button("😎 알아요", key="good", on_click=_rv_answer, args=("good",), width="stretch")

    st.write("")
    st.button("그만하기", on_click=_rv_stop)


# ───────────────────────── 페이지: 퀴즈(4지선다) ─────────────────────────
def _qz_pick(opt):
    qz = st.session_state.qz
    item = qz["items"][qz["i"]]
    qz["picked"] = opt
    ok = opt == item["ans"]
    add_xp(XP["quiz_ok"] if ok else XP["quiz_ng"])
    qz["xp"] = qz.get("xp", 0) + (XP["quiz_ok"] if ok else XP["quiz_ng"])
    if ok:
        qz["score"] += 1
    else:
        qz["wrong"].append(item)
        if qz["apply"]:
            grade(item["id"], "again")


def _qz_next():
    qz = st.session_state.qz
    qz["i"] += 1
    qz["picked"] = None


def _qz_reset():
    st.session_state.pop("qz", None)


def page_quiz():
    ss = st.session_state
    df = load_df()
    if "qz" not in ss:
        st.subheader("4지선다 퀴즈")
    if len(df) < 4:
        st.info("퀴즈는 카드가 4개 이상 있어야 해.")
        return

    if "qz" not in ss:
        kinds = st.multiselect("종류", KINDS, default=KINDS, key="qz_kinds")
        direction = st.radio("문제", ["영어 보고 뜻 고르기", "뜻 보고 영어 고르기"], horizontal=True)
        n = st.slider("문제 수", 5, 50, 10, 5)
        apply = st.checkbox("틀린 문제는 복습 대상으로 되돌리기", value=True)
        if st.button("시작", type="primary", width="stretch", disabled=not kinds):
            pool = df[df["kind"].isin(kinds)]
            if pool.empty:
                st.info("해당 종류의 카드가 없어.")
                return
            col, qcol = ("back", "front") if direction.startswith("영어") else ("front", "back")
            items = []
            for _, r in pool.sample(min(n, len(pool))).iterrows():
                ans = r[col]
                cand = df[(df["id"] != r["id"]) & (df["kind"] == r["kind"]) & (df[col] != ans)][col].drop_duplicates().tolist()
                if len(cand) < 3:
                    cand = df[(df["id"] != r["id"]) & (df[col] != ans)][col].drop_duplicates().tolist()
                opts = random.sample(cand, min(3, len(cand))) + [ans]
                random.shuffle(opts)
                items.append(dict(id=int(r["id"]), q=r[qcol], ans=ans, opts=opts,
                                  kind=r["kind"], front=r["front"], back=r["back"]))
            ss.qz = dict(items=items, i=0, score=0, picked=None, apply=apply, wrong=[])
            st.rerun()
        return

    qz = ss.qz
    items = qz["items"]

    if qz["i"] >= len(items):
        show(card_html(f"{qz['score']} / {len(items)}", f"점수 · +{qz.get('xp', 0)} XP"))
        if qz["wrong"]:
            st.markdown("##### 틀린 것")
            show("".join(
                f'<div style="background:#fff;border:1.5px solid {LINE};border-radius:14px;padding:10px 14px;margin-bottom:8px;">'
                f'<b style="color:{INK}">{esc(w["front"])}</b><div style="color:{MUTED};font-size:14px;">{esc(w["back"])}</div></div>'
                for w in qz["wrong"]))
        else:
            st.balloons()
        st.button("다시 하기", type="primary", on_click=_qz_reset, width="stretch")
        return

    item = items[qz["i"]]
    show(progress_html(qz["i"] / len(items), f"{qz['i'] + 1}/{len(items)} · 맞힌 {qz['score']}"))
    show(card_html(item["q"], item["kind"]))

    with st.container(key="opts"):
        for k, opt in enumerate(item["opts"]):
            if qz["picked"] is None:
                st.button(opt, key=f"qz_{qz['i']}_{k}", on_click=_qz_pick, args=(opt,), width="stretch")
            else:
                if opt == item["ans"]:
                    bg, fg, bd, mark = "#E6F6EF", "#0B4A38", "#7CCFAE", "✅ "
                elif opt == qz["picked"]:
                    bg, fg, bd, mark = "#FDECEC", "#9B2C2C", "#F2A7A7", "❌ "
                else:
                    bg, fg, bd, mark = "#fff", MUTED, LINE, ""
                show(f'<div style="background:{bg};color:{fg};border:1.5px solid {bd};border-radius:14px;'
                     f'padding:13px 18px;margin-bottom:10px;font-weight:600;">{mark}{esc(opt)}</div>')

    if qz["picked"] is not None:
        speak_button(item["front"])
        st.button("다음 →", type="primary", on_click=_qz_next, width="stretch")
    st.write("")
    st.button("그만하기", on_click=_qz_reset)


# ───────────────────────── 페이지: 목록(검색/수정/삭제) ─────────────────────────
def page_list():
    st.subheader("내 단어장")
    tab1, tab2 = st.tabs(["목록", "백업 · 복원"])
    with tab1:
        _list_cards()
    with tab2:
        page_backup()


def _list_cards():
    ss = st.session_state
    ss.setdefault("ed_ver", 0)
    df = load_df()
    if df.empty:
        st.info("카드가 없어.")
        return

    q = st.text_input("🔍 검색", placeholder="영어, 뜻, 예문")
    kinds = st.multiselect("종류", KINDS, default=KINDS, key="list_kinds")
    view = df[df["kind"].isin(kinds)]
    if q:
        m = False
        for col in ["front", "back", "example", "note"]:
            m = m | view[col].fillna("").str.contains(q, case=False, regex=False)
        view = view[m]
    st.caption(f"{len(view)}개 · 셀을 눌러 바로 수정하고 아래 저장 버튼을 눌러")

    view = view[["id", "kind", "front", "back", "example", "note", "box", "due"]].copy()
    view.insert(0, "삭제", False)
    edited = st.data_editor(
        view,
        key=f"editor_{ss.ed_ver}",
        hide_index=True,
        width="stretch",
        disabled=["id", "box", "due"],
        column_config={
            "삭제": st.column_config.CheckboxColumn("삭제", width="small"),
            "id": None,
            "kind": st.column_config.SelectboxColumn("종류", options=KINDS, required=True),
            "front": st.column_config.TextColumn("영어", required=True),
            "back": st.column_config.TextColumn("뜻", required=True),
            "example": "예문",
            "note": "메모",
            "box": st.column_config.NumberColumn("단계"),
            "due": "다음 복습",
        },
    )

    if st.button("변경사항 저장", type="primary", width="stretch"):
        orig = view.set_index("id")
        conn = get_conn()
        n_upd = n_del = 0
        fields = ["kind", "front", "back", "example", "note"]
        for _, r in edited.iterrows():
            cid = int(r["id"])
            if r["삭제"]:
                conn.execute("DELETE FROM cards WHERE id=?", (cid,))
                n_del += 1
            elif any(str(r[f] or "") != str(orig.loc[cid, f] or "") for f in fields):
                conn.execute(
                    "UPDATE cards SET kind=?, front=?, back=?, example=?, note=? WHERE id=?",
                    (*[str(r[f] or "").strip() for f in fields], cid),
                )
                n_upd += 1
        conn.commit()
        ss.ed_ver += 1
        ss.list_msg = f"수정 {n_upd}개 · 삭제 {n_del}개"
        st.rerun()

    if ss.get("list_msg"):
        st.success(ss.pop("list_msg"))

    with st.expander("선택한 카드 복습 단계 초기화"):
        st.caption("목록에 보이는 카드 전부를 0단계로 되돌려 오늘부터 다시 복습해.")
        if st.button("보이는 카드 초기화"):
            ids = [int(i) for i in view["id"]]
            conn = get_conn()
            conn.executemany("UPDATE cards SET box=0, due=? WHERE id=?",
                             [(today().isoformat(), i) for i in ids])
            conn.commit()
            st.success(f"{len(ids)}개 초기화")
            st.rerun()


# ───────────────────────── 페이지: 백업 ─────────────────────────
def page_backup():
    df = load_df()

    st.markdown("##### 내보내기")
    st.download_button(
        "CSV로 다운로드",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"vocab_{today().isoformat()}.csv",
        mime="text/csv",
        width="stretch",
        disabled=df.empty,
    )

    st.markdown("##### 가져오기")
    st.caption("필수 열: `front`(영어), `back`(뜻) · 선택: `kind`, `example`, `note`, `box`, `due` (이 앱에서 받은 CSV는 진도까지 복원돼)")
    up = st.file_uploader("CSV 파일", type=["csv"])
    if up and st.button("가져오기", type="primary", width="stretch"):
        try:
            new = pd.read_csv(up, encoding="utf-8-sig").fillna("")
        except UnicodeDecodeError:
            up.seek(0)
            new = pd.read_csv(up, encoding="cp949").fillna("")
        if not {"front", "back"} <= set(new.columns):
            st.error("front, back 열이 필요해.")
        else:
            added = 0
            for _, r in new.iterrows():
                box = int(r["box"]) if "box" in new and str(r["box"]).strip() != "" else 0
                due = str(r["due"]) if "due" in new and str(r["due"]).strip() else None
                ok, _ = add_card(r.get("kind", "단어") or "단어", r["front"], r["back"],
                                 r.get("example", ""), r.get("note", ""), box, due)
                added += ok
            st.success(f"{added}개 추가 (중복 {len(new) - added}개 건너뜀)")

    st.markdown("##### 전체 삭제")
    with st.expander("⚠️ 위험 구역"):
        sure = st.checkbox("정말 모든 카드를 삭제할게")
        if st.button("전체 삭제", disabled=not sure):
            conn = get_conn()
            conn.execute("DELETE FROM cards")
            conn.commit()
            st.success("전부 삭제됨")
            st.rerun()


# ───────────────────────── 메인 ─────────────────────────
if st.session_state.get("page") not in PAGES:
    st.session_state.page = PAGES[0]
with st.container(key="nav"):
    page = st.radio("메뉴", PAGES, key="page", horizontal=True, label_visibility="collapsed")

{
    "🏠 홈": page_home,
    "🃏 복습": page_review,
    "➕ 추가": page_add,
    "📝 퀴즈": page_quiz,
    "📋 목록": page_list,
}[page]()
