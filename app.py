"""
Zeya Success Dashboard (Streamlit)
------------------------------------------------------
Scope: one pilot clinic, two illustrative success metrics —
  1. After-hours coverage
  2. Cancellation-to-reschedule conversion

Features:
  - Clinic selector (single pilot clinic for now)
  - Plain-language "how we calculate this" for each metric
  - Week-over-week trend with an interpretation line
  - A week scrubber that drives a live example conversation per metric

This is a PITCH PROTOTYPE. All numbers and conversations are
fabricated/illustrative. It shows the shape of the output — not the
extraction pipeline, join logic, or data architecture behind it.

Run with:
    pip install streamlit plotly
    streamlit run app.py
"""

import textwrap
import streamlit as st
import plotly.graph_objects as go

# ----------------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------------
st.set_page_config(page_title="Zeya Success Dashboard", page_icon="🩺", layout="wide")

# ----------------------------------------------------------------------
# THEME TOKENS — matched to zeya.health
# ----------------------------------------------------------------------
BG_START = "#F5F9FE"
BG_END = "#E9F2FC"
NAVY = "#0B1B36"
SKY = "#2E9EE8"
MINT = "#34E8B3"
SLATE = "#66738C"
CARD = "#FFFFFF"
CARD_BORDER = "#E3EBF5"
SHADOW = "0 8px 30px rgba(46, 158, 232, 0.10)"
AMBER = "#E8A93E"  # used for "not yet at goal" states, sparingly

st.markdown(textwrap.dedent(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', sans-serif; color: {NAVY}; }}
.stApp {{ background: linear-gradient(135deg, {BG_START} 0%, {BG_END} 100%); }}
#MainMenu, footer, header {{visibility: hidden;}}

.block-container {{
    max-width: 1080px;
    margin: 0 auto;
    padding-top: 2.5rem;
    padding-bottom: 3rem;
}}

.zh-pill {{ display:inline-flex; align-items:center; gap:8px; background:#FFFFFF; border:1px solid {CARD_BORDER};
    border-radius:100px; padding:8px 18px; font-size:13px; font-weight:600; color:{SLATE}; box-shadow:{SHADOW}; margin-bottom:18px; }}
.zh-pill .dot {{ width:8px; height:8px; border-radius:50%; background:{MINT}; display:inline-block; }}

.zh-h1 {{ font-weight:800; font-size:38px; line-height:1.15; margin:0 0 4px 0; color:{NAVY}; letter-spacing:-0.01em; }}
.zh-h1 .grad {{ background:linear-gradient(90deg, {SKY} 0%, {MINT} 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }}
.zh-sub {{ font-size:15px; color:{SLATE}; font-weight:500; max-width:65ch; margin:10px 0 4px; }}
.zh-fineprint {{ font-size:12px; color:{SLATE}; opacity:0.75; font-weight:500; margin:12px 0 8px 0; }}

.zh-card {{ background:{CARD}; border:1px solid {CARD_BORDER}; border-radius:20px; padding:24px 26px; box-shadow:{SHADOW}; }}
.zh-card-tight {{ background:{CARD}; border:1px solid {CARD_BORDER}; border-radius:16px; padding:16px 20px; box-shadow:{SHADOW}; }}

.zh-metric-num {{ font-weight:800; font-size:40px; line-height:1;
    background:linear-gradient(90deg, {SKY} 0%, {MINT} 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }}
.zh-metric-label {{ font-size:13.5px; color:{SLATE}; font-weight:500; margin-top:8px; line-height:1.5; }}
.zh-metric-week {{ font-size:11.5px; color:{SLATE}; opacity:0.7; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; }}

.zh-section-head {{ display:flex; align-items:center; gap:12px; margin:36px 0 14px 0; }}
.zh-step-badge {{ display:inline-flex; align-items:center; background:#FFFFFF; border:1px solid {CARD_BORDER}; border-radius:100px;
    padding:5px 14px; font-size:12px; font-weight:700; color:{SKY}; box-shadow:{SHADOW}; }}
.zh-h2 {{ font-weight:700; font-size:21px; margin:0; color:{NAVY}; }}
.zh-note {{ font-size:13.5px; color:{SLATE}; font-weight:500; max-width:70ch; margin-bottom:14px; }}

.zh-interp {{ background:linear-gradient(135deg, rgba(46,158,232,0.08), rgba(52,232,179,0.10)); border:1px solid rgba(46,158,232,0.18);
    border-radius:14px; padding:14px 18px; font-size:14px; font-weight:600; color:{NAVY}; margin:14px 0 18px 0; }}
.zh-interp span {{ color:{SKY}; font-weight:700; }}

.zh-formula-label {{ font-size:12px; font-weight:700; color:{SLATE}; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:6px; }}
.zh-formula {{ font-size:13.5px; color:{NAVY}; font-weight:500; line-height:1.5; }}

.zh-thread-meta {{ font-size:11px; font-weight:600; color:{SLATE}; opacity:0.65; margin-bottom:14px; letter-spacing:0.02em; }}
.zh-bubble {{ padding:11px 15px; border-radius:14px; font-size:13.5px; font-weight:500; line-height:1.5; margin-bottom:8px; }}
.zh-bubble.patient {{ background:#F3F6FB; border:1px solid {CARD_BORDER}; color:{NAVY}; }}
.zh-bubble.bot {{ background:linear-gradient(135deg, rgba(46,158,232,0.10), rgba(52,232,179,0.14)); border:1px solid rgba(46,158,232,0.18); color:{NAVY}; }}
.zh-who {{ display:block; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:{SLATE}; opacity:0.7; margin-bottom:3px; }}
.zh-tag {{ font-size:11px; font-weight:600; padding:5px 11px; border-radius:100px; background:#FFFFFF; border:1px solid {CARD_BORDER};
    color:{SLATE}; display:inline-block; margin-bottom:10px; }}
.zh-tag b {{ color:{SKY}; font-weight:700; }}
.zh-outcome-pill {{ font-size:12px; font-weight:700; color:#FFFFFF; padding:7px 15px; border-radius:100px; display:inline-block; margin-top:6px;
    background:linear-gradient(90deg, {SKY} 0%, {MINT} 100%); }}
.zh-outcome-pill.pending {{ background:{AMBER}; }}

.zh-lang-row {{ display:flex; gap:14px; margin-top:4px; }}
.zh-lang-card {{ flex:1; background:#F8FAFD; border:1px solid {CARD_BORDER}; border-radius:14px; padding:14px 16px; }}
.zh-lang-tag {{ font-size:10.5px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:{SKY}; margin-bottom:6px; }}
.zh-lang-time {{ font-size:12px; font-weight:600; color:{SLATE}; margin-top:8px; }}

.zh-group-divider {{ display:flex; align-items:center; gap:14px; margin:50px 0 8px 0; }}
.zh-group-divider .line {{ flex:1; height:1px; background:{CARD_BORDER}; }}
.zh-group-label {{ font-size:12px; font-weight:700; color:{SLATE}; text-transform:uppercase; letter-spacing:0.06em; white-space:nowrap; }}
.zh-group-caption {{ font-size:12.5px; color:{SLATE}; font-weight:500; opacity:0.85; margin:0 0 20px 0; max-width:72ch; }}

.zh-footer-note {{ font-size:12px; color:{SLATE}; font-weight:500; max-width:62ch; margin-top:40px; border-top:1px solid {CARD_BORDER}; padding-top:18px; }}
</style>
"""), unsafe_allow_html=True)

# ----------------------------------------------------------------------
# DATA — illustrative / fabricated, 12-week pilot window
# ----------------------------------------------------------------------
weeks = list(range(1, 13))

after_hours_coverage = [9, 13, 18, 22, 27, 31, 36, 40, 44, 47, 50, 52.7]      # %
after_hours_response_time = [38, 35, 32, 29, 26, 22, 18, 15, 12, 9, 7, 5]      # minutes

reschedule_pct = [41, 43, 46, 49, 52, 55, 58, 61, 64, 67, 69, 71]              # %
total_cancellations = [17, 16, 15, 17, 14, 16, 15, 14, 13, 15, 14, 13]

ailments = ["an ear infection", "a bad back spasm", "chest congestion",
            "a migraine that won't let up", "a sprained ankle from football", "a persistent cough"]
slot_times = ["8:00am", "8:30am", "9:00am", "7:45am"]
after_hours_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
after_hours_times = ["11:52pm", "12:20am", "1:15am", "11:05pm", "2:30am",
                      "10:40pm", "12:48am", "11:30pm", "1:50am", "10:58pm", "12:05am", "11:20pm"]

cancel_reasons = ["something came up at work", "I'm not feeling well enough to come in",
                   "a family emergency", "I got double-booked with school pickup",
                   "my flight got moved up", "I forgot until the last minute"]
orig_times = ["4:00pm", "11:00am", "2:30pm", "9:30am", "5:00pm", "1:00pm"]
alt_days = ["Thursday", "Friday", "Monday", "Wednesday", "Saturday", "Tuesday"]
alt_times = ["10:30am", "2:00pm", "11:15am", "4:30pm", "9:00am", "3:15pm"]
cancel_days = ["MON", "TUE", "WED", "THU", "FRI"]


def after_hours_chat(week):
    i = week - 1
    ailment = ailments[i % len(ailments)]
    slot = slot_times[i % len(slot_times)]
    day = after_hours_days[i % len(after_hours_days)]
    tstamp = after_hours_times[i % len(after_hours_times)]
    resp = after_hours_response_time[i]
    success = resp <= 5
    thread_id = 5100 + week * 13
    return {
        "meta": f"THREAD #{thread_id} · {day} {tstamp} SGT",
        "ailment": ailment, "slot": slot, "resp": resp, "success": success,
    }


def reschedule_chat(week):
    i = week - 1
    reason = cancel_reasons[i % len(cancel_reasons)]
    orig = orig_times[i % len(orig_times)]
    day = alt_days[i % len(alt_days)]
    alt_t = alt_times[i % len(alt_times)]
    cday = cancel_days[i % len(cancel_days)]
    total = total_cancellations[i]
    pct = reschedule_pct[i]
    converted = round(total * pct / 100)
    thread_id = 4800 + week * 11
    return {
        "meta": f"THREAD #{thread_id} · {cday} 14:02 SGT",
        "reason": reason, "orig": orig, "day": day, "alt_t": alt_t,
        "total": total, "converted": converted, "pct": pct,
    }


def after_hours_interp(week):
    if week <= 3:
        return "Early weeks: coverage is still building as after-hours volume ramps up and typical query types get established."
    if week <= 6:
        return "Coverage climbs past a quarter of after-hours messages as routine requests get resolved without waiting for staff."
    if week <= 9:
        return "More than 4 in 10 after-hours messages now get answered within 5 minutes — patients are booking before the clinic even reopens."
    return "Coverage stabilises above 50%, meaning after-hours is no longer a blind spot for the clinic."


def reschedule_interp(week):
    if week <= 3:
        return "Just over 4 in 10 cancellations are recovered — many still fall through without a nudge to rebook."
    if week <= 6:
        return "Recovery climbs past 50% as the assistant proactively offers a new time in the same thread as the cancellation."
    if week <= 9:
        return "Roughly 6 in 10 cancellations now convert into a new booking, recovering visits that would otherwise sit empty."
    return "Recovery holds around 70%, turning most cancellations into a rebooked visit instead of a lost one."


# --- Care-quality signals: empathy acknowledgment + response equity ---
# Framed deliberately as conversational signals, not clinical patient-reported
# outcomes (PROs) — those require validated instruments (e.g. PROMIS, EQ-5D).

empathy_rate = [58, 61, 65, 68, 72, 75, 79, 82, 84, 86, 88, 89]  # % of concern messages acknowledged before logistics

distress_msgs = [
    "I'm really worried about this pain, it doesn't feel right",
    "This has been bothering me for weeks now and I'm getting anxious",
    "I'm in quite a bit of discomfort right now",
    "I've been pretty stressed about how slow this recovery's been",
    "I'm scared this isn't healing the way it should",
    "It's frustrating, this keeps coming back no matter what I do",
]
acknowledgments = [
    "That sounds really uncomfortable — let's get you seen soon.",
    "I'm sorry you've been dealing with this, let's get it looked at.",
    "That sounds stressful, let's find you a slot quickly.",
    "I hear you — let's make sure someone looks at this soon.",
    "That's understandably worrying, let's get this sorted for you.",
    "That sounds frustrating — let's get you back in to check on it.",
]
slot_times2 = ["11:00am", "3:30pm", "9:15am", "1:00pm", "4:45pm", "10:00am"]


def empathy_chat(week):
    i = week - 1
    concern = distress_msgs[i % len(distress_msgs)]
    ack = acknowledgments[i % len(acknowledgments)]
    slot = slot_times2[i % len(slot_times2)]
    rate = empathy_rate[i]
    success = rate >= 75
    thread_id = 5300 + week * 9
    return {
        "meta": f"THREAD #{thread_id} · patient message",
        "concern": concern, "ack": ack, "slot": slot, "success": success,
    }


def empathy_interp(week):
    if week <= 3:
        return "Early weeks: the assistant often moves straight to logistics before acknowledging what the patient is going through."
    if week <= 6:
        return "Acknowledgment starts appearing more consistently, though it's not yet the default response."
    if week <= 9:
        return "Most concerning messages now get acknowledged before the assistant offers a time slot."
    return "Nearly 9 in 10 concerns are acknowledged before logistics — the norm rather than the exception."


# response equity: gap in average reply time between English and the
# fastest-improving non-English language thread that week (minutes, lower = better)
equity_gap = [18, 16, 14, 12, 10, 9, 7, 6, 5, 4, 3, 2]
english_response = [4, 4, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2]
other_languages = ["Mandarin", "Malay", "Tamil", "Bahasa Indonesia"]
lang_concerns = [
    "hi, do you have appointments open tomorrow",
    "can I move my appointment to next week",
    "is Dr. Lim available on Friday",
    "how much does a follow-up visit cost",
]


def equity_chat(week):
    i = week - 1
    lang = other_languages[i % len(other_languages)]
    concern = lang_concerns[i % len(lang_concerns)]
    gap = equity_gap[i]
    eng_time = english_response[i]
    other_time = eng_time + gap
    success = gap <= 5
    thread_id = 5500 + week * 7
    return {
        "meta": f"THREAD #{thread_id} · {lang} conversation, same week",
        "lang": lang, "concern": concern, "gap": gap,
        "eng_time": eng_time, "other_time": other_time, "success": success,
    }


def equity_interp(week):
    if week <= 3:
        return "Non-English threads wait noticeably longer for a reply than English ones — a real gap in experience by language."
    if week <= 6:
        return "The gap narrows as multilingual handling improves, though English threads are still answered a little faster on average."
    if week <= 9:
        return "Response times are converging — most languages are now answered within a few minutes of each other."
    return "The gap has nearly closed: patients get a comparably fast reply regardless of which language they message in."


def trend_chart(y_values, selected_week, y_suffix="%"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weeks, y=y_values, mode="lines+markers",
        line=dict(color=SKY, width=3, shape="spline"),
        marker=dict(size=6, color=MINT, line=dict(width=2, color="#FFFFFF")),
        fill="tozeroy", fillcolor="rgba(46, 158, 232, 0.08)",
        hovertemplate="Week %{x}<br>%{y}" + y_suffix + "<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[selected_week], y=[y_values[selected_week - 1]], mode="markers",
        marker=dict(size=13, color=NAVY, line=dict(width=2, color="#FFFFFF")),
        hovertemplate="Week %{x}<br>%{y}" + y_suffix + "<extra></extra>", showlegend=False,
    ))
    fig.add_vline(x=selected_week, line_width=1, line_dash="dot", line_color=CARD_BORDER)
    fig.update_layout(
        height=200, margin=dict(l=10, r=10, t=10, b=30),
        plot_bgcolor=CARD, paper_bgcolor=CARD,
        xaxis=dict(title="Week", showgrid=False, tickfont=dict(size=10.5, family="Plus Jakarta Sans", color=SLATE)),
        yaxis=dict(showgrid=True, gridcolor=CARD_BORDER, ticksuffix=y_suffix, tickfont=dict(size=10.5, family="Plus Jakarta Sans", color=SLATE)),
        font=dict(family="Plus Jakarta Sans"), showlegend=False,
    )
    return fig


# ----------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------
st.markdown('<div class="zh-pill"><span class="dot"></span>Zeya Health · Chat Ops</div>', unsafe_allow_html=True)
st.markdown('<div class="zh-h1">Zeya Success <span class="grad">Dashboard</span></div>', unsafe_allow_html=True)
st.markdown('<div class="zh-sub">How conversations turn into measurable outcomes, clinic by clinic, week by week.</div>', unsafe_allow_html=True)
st.markdown('<div class="zh-fineprint">Illustrative figures — simulated pilot data for preview purposes, not a live report.</div>', unsafe_allow_html=True)

col_sel, col_gap = st.columns([2, 3])
with col_sel:
    clinic = st.selectbox("Clinic", ["Tanjong Physio & Wellness — 12-week pilot"])
    st.caption("This preview covers our one active pilot. New clinics appear here as they onboard.")

st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
selected_week = st.slider("Scrub through the pilot", min_value=1, max_value=12, value=12,
                           format="Week %d", help="Drag to see how each metric — and a live example conversation — looked in a given week.")

# ----------------------------------------------------------------------
# SECTION 1 — AFTER-HOURS COVERAGE
# ----------------------------------------------------------------------
st.markdown(textwrap.dedent("""
<div class="zh-section-head">
    <span class="zh-step-badge">METRIC 01</span>
    <h2 class="zh-h2">After-hours coverage</h2>
</div>
"""), unsafe_allow_html=True)

col1, col2 = st.columns([1, 2])
with col1:
    val = after_hours_coverage[selected_week - 1]
    st.markdown(textwrap.dedent(f"""
    <div class="zh-card">
        <div class="zh-metric-week">Week {selected_week}</div>
        <div class="zh-metric-num">{val}%</div>
        <div class="zh-metric-label">of after-hours messages answered within 5 minutes</div>
    </div>
    """), unsafe_allow_html=True)
    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    st.markdown(textwrap.dedent(f"""
    <div class="zh-card-tight">
        <div class="zh-formula-label">How we calculate this</div>
        <div class="zh-formula">After-hours messages answered within 5 minutes, divided by all messages received outside clinic hours (9am–6pm), that week.</div>
    </div>
    """), unsafe_allow_html=True)
with col2:
    st.plotly_chart(trend_chart(after_hours_coverage, selected_week), use_container_width=True, config={"displayModeBar": False})

st.markdown(f'<div class="zh-interp"><span>Week {selected_week} —</span> {after_hours_interp(selected_week)}</div>', unsafe_allow_html=True)

ah = after_hours_chat(selected_week)
outcome_class = "" if ah["success"] else "pending"
outcome_text = (f"Counted: after-hours message, answered within 5 min"
                if ah["success"] else
                f"Logged: after-hours message, answered in {ah['resp']}m (goal: under 5 min)")

st.markdown(textwrap.dedent(f"""
<div class="zh-card">
    <div class="zh-thread-meta">{ah['meta']}</div>
    <div class="zh-bubble patient"><span class="zh-who">Patient</span>Hi, sorry it's late — I've got {ah['ailment']}, can I book something now or does this have to wait?</div>
    <div class="zh-tag"><b>After-hours flag</b> · outside clinic hours (9am–6pm)</div><br>
    <div class="zh-bubble bot"><span class="zh-who">Zeya Assistant</span>You can book right now — I don't need the clinic to be open. I have a {ah['slot']} slot tomorrow, would that work?</div>
    <div class="zh-tag"><b>Response time</b> · {ah['resp']}m after hours</div><br>
    <div class="zh-bubble patient"><span class="zh-who">Patient</span>Yes please, thank you.</div>
    <div class="zh-outcome-pill {outcome_class}">{outcome_text}</div>
</div>
"""), unsafe_allow_html=True)

# ----------------------------------------------------------------------
# SECTION 2 — RESCHEDULE CONVERSION
# ----------------------------------------------------------------------
st.markdown(textwrap.dedent("""
<div class="zh-section-head">
    <span class="zh-step-badge">METRIC 02</span>
    <h2 class="zh-h2">Cancellation → reschedule conversion</h2>
</div>
"""), unsafe_allow_html=True)

col3, col4 = st.columns([1, 2])
with col3:
    rval = reschedule_pct[selected_week - 1]
    st.markdown(textwrap.dedent(f"""
    <div class="zh-card">
        <div class="zh-metric-week">Week {selected_week}</div>
        <div class="zh-metric-num">{rval}%</div>
        <div class="zh-metric-label">of cancellations rebooked within 7 days</div>
    </div>
    """), unsafe_allow_html=True)
    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    st.markdown(textwrap.dedent(f"""
    <div class="zh-card-tight">
        <div class="zh-formula-label">How we calculate this</div>
        <div class="zh-formula">Cancellations that turn into a new confirmed booking within 7 days, divided by all cancellations recorded that week.</div>
    </div>
    """), unsafe_allow_html=True)
with col4:
    st.plotly_chart(trend_chart(reschedule_pct, selected_week), use_container_width=True, config={"displayModeBar": False})

st.markdown(f'<div class="zh-interp"><span>Week {selected_week} —</span> {reschedule_interp(selected_week)}</div>', unsafe_allow_html=True)

rc = reschedule_chat(selected_week)
st.markdown(textwrap.dedent(f"""
<div class="zh-card">
    <div class="zh-thread-meta">{rc['meta']}</div>
    <div class="zh-bubble patient"><span class="zh-who">Patient</span>Hi, I need to cancel my {rc['orig']} today — {rc['reason']}.</div>
    <div class="zh-tag"><b>Intent</b> · Cancellation request</div><br>
    <div class="zh-bubble bot"><span class="zh-who">Zeya Assistant</span>No problem, I've cancelled your {rc['orig']}. Would you like to find another time this week?</div>
    <div class="zh-tag"><b>Response time</b> · under 2 minutes from cancellation</div><br>
    <div class="zh-bubble patient"><span class="zh-who">Patient</span>Yeah, I'd still like to come in. Anything {rc['day']}?</div>
    <div class="zh-bubble bot"><span class="zh-who">Zeya Assistant</span>{rc['day']} {rc['alt_t']} is open — want me to book that?</div>
    <div class="zh-bubble patient"><span class="zh-who">Patient</span>Yes, that works, thanks.</div>
    <div class="zh-outcome-pill">Counted: {rc['converted']} of {rc['total']} cancellations recovered this week</div>
</div>
"""), unsafe_allow_html=True)

st.markdown(textwrap.dedent("""
<div class="zh-group-divider"><span class="line"></span><span class="zh-group-label">Care quality signals</span><span class="line"></span></div>
<div class="zh-group-caption">These read conversational behavior, not clinical status — a proxy for experience, not a
substitute for validated patient-reported outcome measures.</div>
"""), unsafe_allow_html=True)

# ----------------------------------------------------------------------
# SECTION 3 — EMPATHY ACKNOWLEDGMENT RATE
# ----------------------------------------------------------------------
st.markdown(textwrap.dedent("""
<div class="zh-section-head">
    <span class="zh-step-badge">SIGNAL 03</span>
    <h2 class="zh-h2">Empathy acknowledgment rate</h2>
</div>
"""), unsafe_allow_html=True)

col5, col6 = st.columns([1, 2])
with col5:
    eval_ = empathy_rate[selected_week - 1]
    st.markdown(textwrap.dedent(f"""
    <div class="zh-card">
        <div class="zh-metric-week">Week {selected_week}</div>
        <div class="zh-metric-num">{eval_}%</div>
        <div class="zh-metric-label">of worried or uncomfortable messages acknowledged before logistics</div>
    </div>
    """), unsafe_allow_html=True)
    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    st.markdown(textwrap.dedent(f"""
    <div class="zh-card-tight">
        <div class="zh-formula-label">How we calculate this</div>
        <div class="zh-formula">Messages expressing worry, discomfort, or frustration where the assistant's first reply acknowledges the concern before offering a time or logistics, divided by all such messages that week.</div>
    </div>
    """), unsafe_allow_html=True)
with col6:
    st.plotly_chart(trend_chart(empathy_rate, selected_week), use_container_width=True, config={"displayModeBar": False})

st.markdown(f'<div class="zh-interp"><span>Week {selected_week} —</span> {empathy_interp(selected_week)}</div>', unsafe_allow_html=True)

ec = empathy_chat(selected_week)
if ec["success"]:
    body = f"""<div class="zh-bubble patient"><span class="zh-who">Patient</span>{ec['concern']}</div>
<div class="zh-tag"><b>Sentiment</b> · concern / worry detected</div><br>
<div class="zh-bubble bot"><span class="zh-who">Zeya Assistant</span>{ec['ack']} I have a slot at {ec['slot']} tomorrow if you'd like it.</div>
<div class="zh-tag"><b>Acknowledgment</b> · present, before logistics</div><br>
<div class="zh-outcome-pill">Counted: concern acknowledged before logistics</div>"""
else:
    body = f"""<div class="zh-bubble patient"><span class="zh-who">Patient</span>{ec['concern']}</div>
<div class="zh-tag"><b>Sentiment</b> · concern / worry detected</div><br>
<div class="zh-bubble bot"><span class="zh-who">Zeya Assistant</span>I have a slot at {ec['slot']} tomorrow, would that work?</div>
<div class="zh-tag"><b>Acknowledgment</b> · missing from first reply</div><br>
<div class="zh-bubble patient"><span class="zh-who">Patient</span>Okay... I guess so.</div>
<div class="zh-bubble bot"><span class="zh-who">Zeya Assistant</span>{ec['ack']}</div>
<div class="zh-outcome-pill pending">Logged: concern acknowledged, but only after logistics</div>"""

st.markdown(textwrap.dedent(f"""\
<div class="zh-card">
<div class="zh-thread-meta">{ec['meta']}</div>
{body}
</div>
"""), unsafe_allow_html=True)

# ----------------------------------------------------------------------
# SECTION 4 — RESPONSE EQUITY
# ----------------------------------------------------------------------
st.markdown(textwrap.dedent("""
<div class="zh-section-head">
    <span class="zh-step-badge">SIGNAL 04</span>
    <h2 class="zh-h2">Response equity across languages</h2>
</div>
"""), unsafe_allow_html=True)

col7, col8 = st.columns([1, 2])
with col7:
    gap = equity_gap[selected_week - 1]
    st.markdown(textwrap.dedent(f"""
    <div class="zh-card">
        <div class="zh-metric-week">Week {selected_week}</div>
        <div class="zh-metric-num">{gap} min</div>
        <div class="zh-metric-label">gap in average reply time, fastest vs. slowest-served language (lower is better)</div>
    </div>
    """), unsafe_allow_html=True)
    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    st.markdown(textwrap.dedent(f"""
    <div class="zh-card-tight">
        <div class="zh-formula-label">How we calculate this</div>
        <div class="zh-formula">Difference in average response time between the fastest-served and slowest-served patient language that week. Tracks whether speed of care depends on which language a patient messages in.</div>
    </div>
    """), unsafe_allow_html=True)
with col8:
    st.plotly_chart(trend_chart(equity_gap, selected_week, y_suffix="m"), use_container_width=True, config={"displayModeBar": False})

st.markdown(f'<div class="zh-interp"><span>Week {selected_week} —</span> {equity_interp(selected_week)}</div>', unsafe_allow_html=True)

eq = equity_chat(selected_week)
outcome_class2 = "" if eq["success"] else "pending"
outcome_text2 = (f"Counted: {eq['gap']} min gap — within parity range"
                 if eq["success"] else
                 f"Logged: {eq['gap']} min gap between languages this week (goal: 5 min or under)")

st.markdown(textwrap.dedent(f"""
<div class="zh-card">
    <div class="zh-thread-meta">{eq['meta']}</div>
    <div class="zh-lang-row">
        <div class="zh-lang-card">
            <div class="zh-lang-tag">English thread</div>
            <div class="zh-bubble patient"><span class="zh-who">Patient</span>Hi, do you have anything open this week?</div>
            <div class="zh-lang-time">Answered in {eq['eng_time']} min</div>
        </div>
        <div class="zh-lang-card">
            <div class="zh-lang-tag">{eq['lang']} thread</div>
            <div class="zh-bubble patient"><span class="zh-who">Patient</span>{eq['concern']}</div>
            <div class="zh-lang-time">Answered in {eq['other_time']} min</div>
        </div>
    </div>
    <div class="zh-outcome-pill {outcome_class2}" style="margin-top:14px;">{outcome_text2}</div>
</div>
"""), unsafe_allow_html=True)

# ----------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------
st.markdown(textwrap.dedent("""
<div class="zh-footer-note">
Prototype scoped to four signals and one pilot clinic to preview the shape of the dashboard. The full version connects to a
clinic's real chat and booking data, adds a clinic switcher across a portfolio, and extends to the remaining metrics
(booking conversion, revenue uplift, engagement) using the same underlying approach. Care-quality signals here are conversational
proxies, not validated clinical outcome measures.
</div>
"""), unsafe_allow_html=True)