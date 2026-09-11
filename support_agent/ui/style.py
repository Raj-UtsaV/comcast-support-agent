"""Shared visual design for the support workspace; no external assets needed."""

from html import escape

import streamlit as st


def apply_style():
    st.markdown(
        """<style>
        .stApp { background: #f5f7fb; }
        .block-container { max-width: 1440px; padding-top: 2.5rem; padding-bottom: 3rem; }
        h1, h2, h3 { letter-spacing: -.035em; }
        [data-testid="stSidebar"] { background: #10243b; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
        [data-testid="stSidebar"] label { color: #e4edf7; }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #aebed1; }
        [data-testid="stSidebar"] hr { border-color: #30445b; }
        [data-testid="stSidebar"] .stButton button { background: #1d3853; color: #eef6ff; border-color: #3b526c; }
        .brand { display: flex; gap: 12px; align-items: center; margin: 8px 0 32px; }
        .brand-mark { display: grid; place-items: center; width: 42px; height: 42px;
          background: #9ce8d1; border-radius: 13px; color: #10243b; font-weight: 850; font-size: 23px; }
        .brand-name { color: white; font-weight: 750; font-size: 21px; letter-spacing: -.5px; }
        .brand-sub { color: #aebed1; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; }
        .hero { padding: 34px 38px; border-radius: 22px; margin-bottom: 22px;
          background: radial-gradient(ellipse at 100% 0%, #235e68 0%, transparent 60%), #10243b;
          color: #fff; position: relative; overflow: hidden; }
        .eyebrow { font-size: 11px; font-weight: 750; letter-spacing: 2px; text-transform: uppercase; color: #91e3ce; }
        .hero h1 { color: #fff; font-size: clamp(28px, 3.2vw, 44px); line-height: 1.15; margin: 12px 0; padding: 0; }
        .hero p { color: #c4d5e5; max-width: 620px; margin: 0; font-size: 15px; line-height: 1.7; }
        .hero-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
        .mode-chip { border: 1px solid #628a93; background: #ffffff0d; border-radius: 30px;
          padding: 6px 12px; color: #d8f4ec; font-size: 12px; }
        .workflow { display: flex; gap: 22px; flex-wrap: wrap; margin-top: 25px; color: #d1e3ed; font-size: 12px; }
        .workflow b { color: #9ce8d1; margin-right: 7px; }
        [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 24px; margin-bottom: 22px; }
        [data-testid="stTabs"] [data-baseweb="tab"] { font-weight: 650; padding: 12px 2px; }
        [data-testid="stVerticalBlockBorderWrapper"] > div { border-radius: 18px; }
        [data-testid="stVerticalBlockBorderWrapper"] { background: #fff; border-radius: 18px; }
        .st-key-composer, .st-key-response { background: #fff; border-radius: 18px;
          box-shadow: 0 4px 24px #172b4605; }
        [data-testid="stTextArea"] textarea { line-height: 1.7; }
        .stButton button { border-radius: 10px; min-height: 43px; font-weight: 650; }
        [data-testid="stMetric"] { background: #f1f6f8; padding: 16px; border-radius: 12px; }
        [data-testid="stMetricValue"] { font-size: 23px; }
        [data-testid="stAlert"] { border-radius: 12px; }
        .section-label { color: #087f8c; font-size: 11px; letter-spacing: 1.6px;
          font-weight: 750; text-transform: uppercase; margin-bottom: 8px; }
        .empty-state { padding: 40px 22px; text-align: center; }
        .empty-icon { width: 62px; height: 62px; display: grid; place-items: center; margin: 0 auto 20px;
          border-radius: 18px; background: #e2f3ee; color: #087f8c; font-size: 28px; }
        .empty-state h3 { color: #172b46; font-size: 22px; margin: 0 0 8px; padding: 0; }
        .empty-state p { color: #607189; font-size: 14px; max-width: 390px; margin: auto; line-height: 1.8; }
        .reply-card { padding: 22px; border: 1px solid #c9e8de; border-left: 4px solid #087f8c;
          background: #f1faf6; border-radius: 12px; color: #203c48; line-height: 1.85;
          white-space: pre-wrap; overflow-wrap: anywhere; }
        .workspace-footer { margin-top: 28px; color: #697b91; font-size: 12px; text-align: center; }
        @media (max-width: 700px) {
          .block-container { padding: 1.5rem 1rem; }
          .hero { padding: 25px 22px; }
          .workflow { gap: 12px; }
          .empty-state { padding: 26px 12px; }
        }
        </style>""",
        unsafe_allow_html=True,
    )


def hero(company, demo):
    mode = "Synthetic demo" if demo else "Live model workflow"
    st.markdown(
        '<div class="hero"><div class="hero-top">'
        f'<span class="eyebrow">{escape(company)} · Support workspace</span>'
        f'<span class="mode-chip">{mode}</span></div>'
        '<h1>Thoughtful support.<br>One conversation at a time.</h1>'
        '<p>Understand the request, find relevant context, and prepare a reply '
        'your team can review with confidence.</p>'
        '<div class="workflow"><span><b>01</b> Understand</span>'
        '<span><b>02</b> Find evidence</span><span><b>03</b> Draft &amp; review</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(title, description, icon="✦"):
    st.markdown(
        f'<div class="empty-state"><div class="empty-icon">{escape(icon)}</div>'
        f'<h3>{escape(title)}</h3><p>{escape(description)}</p></div>',
        unsafe_allow_html=True,
    )


def reply_card(text):
    st.markdown(f'<div class="reply-card">{escape(text)}</div>', unsafe_allow_html=True)
