# ============================================================
# 올리브영 VOC Product Research Dashboard v3 (최종)
# 실행: streamlit run oliveyoung_dashboard_v3_final.py
#
# v3 변경사항 요약
# P0① Relative Impact Score 명시
# P0② Confidence 계산 → 부정 VOC 기준으로 통일
# P0③ RAW VOC 중복 필터 제거 (카테고리만 유지)
# P0④ "실시간" → "필터 변경 시 동적 재계산" 표현 수정
# P0⑤ Impact Score 가중치 설명 추가
# P0⑥ Impact Score 계산 기준 문구 명확화
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── 페이지 설정 ───────────────────────────────────────────────
st.set_page_config(
    page_title="올리브영 VOC Product Research",
    page_icon="🫒",
    layout="wide"
)

# ── 데이터 로드 ───────────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_csv('★oliveyoung_analyzed_260726.csv')
    df['at'] = pd.to_datetime(df['at'])
    return df

df_raw = load_data()
LATEST_DATE = df_raw['at'].max()
TOTAL_RAW   = len(df_raw)

# ── Impact Score 동적 재계산 함수 ─────────────────────────────
# P0④ "실시간" → "필터 변경 시 동적 재계산"
# P0② Confidence 계산 모집단 → 부정 VOC 기준으로 통일
#      (Severity, Frequency, Confidence 모두 동일 모집단 적용)
# 실무 확장 시: pd.read_csv → pd.read_sql(query, db_conn) 교체로
#              DB 연동 가능한 구조로 설계됨 (캐시/갱신 전략 별도 필요)

TARGET_CATS = [
    '속도/렉', '로그인/계정', '배송', '앱UI/UX', '결제/구매',
    '쿠폰/혜택', '광고/알림', '고객지원', '재고/품절'
]

def calc_impact_score(data):
    """
    Relative Impact Score 계산 (필터 변경 시 동적 재계산)

    - 모집단: 입력 데이터의 부정 VOC 전체
    - 공식: (Severity/4 × 0.5) + (Frequency × 0.3) + (Confidence × 0.2)
    - 가중치 근거: 심각도(50%) 최우선 / 빈도(30%) 보조 / AI 분석 신뢰도(20%) 품질 보정
    - P0①: 기간이 바뀌면 기준이 재설정되는 상대 점수 (Relative)
    - P0⑥: 기간 필터만 모집단 결정 (대상/Severity 필터와 독립 — P1에서 분리 예정)
    - 이 점수는 개선 검토 순서 탐색을 위한 휴리스틱 지표이며,
      객관적 진실을 나타내는 절대 점수가 아님
    """
    neg = data[data['sentiment'] == '부정']
    total_neg = len(neg)
    if total_neg == 0:
        return pd.DataFrame()

    rows = []
    for cat in TARGET_CATS:
        # P0②: Severity, Frequency, Confidence 모두 부정 VOC 기준
        cat_neg = neg[neg['sub_category'] == cat]
        if len(cat_neg) == 0:
            continue

        sev  = cat_neg['severity'].mean() / 4
        freq = len(cat_neg) / total_neg
        conf = (
            len(cat_neg[cat_neg['confidence_level'] == '높음']) / len(cat_neg)
        )
        impact = (sev * 0.5) + (freq * 0.3) + (conf * 0.2)

        cat_all = data[data['sub_category'] == cat]

        top_insight = (
            cat_neg['product_insight'].dropna().value_counts().index[0]
            if len(cat_neg['product_insight'].dropna()) > 0 else '-'
        )
        top_rec = (
            cat_neg['recommendation'].dropna().value_counts().index[0]
            if len(cat_neg['recommendation'].dropna()) > 0 else '-'
        )
        top_kpi = (
            cat_neg['expected_kpi'].dropna().value_counts().index[0]
            if len(cat_neg['expected_kpi'].dropna()) > 0 else '-'
        )
        top_journey = (
            cat_neg['user_journey_stage'].mode()[0]
            if len(cat_neg) > 0 else '-'
        )

        rows.append({
            'sub_category':         cat,
            'main_category':        cat_all['main_category'].mode()[0] if len(cat_all) > 0 else '',
            'total_count':          len(cat_all),
            'neg_count':            len(cat_neg),
            'avg_severity':         round(cat_neg['severity'].mean(), 2),
            'frequency_ratio':      round(freq * 100, 1),
            'conf_ratio':           round(conf * 100, 1),
            'top_journey_stage':    top_journey,
            'top_product_insight':  top_insight,
            'top_recommendation':   top_rec,
            'top_kpi':              top_kpi,
            'impact_raw':           round(impact, 4)
        })

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows).sort_values('impact_raw', ascending=False)
    min_s, max_s = result['impact_raw'].min(), result['impact_raw'].max()
    result['impact_score'] = (
        ((result['impact_raw'] - min_s) / (max_s - min_s) * 100).round(1)
        if max_s > min_s else 100.0
    )
    return result.reset_index(drop=True)


# ── 헤더 ─────────────────────────────────────────────────────
st.markdown("## 🫒 OLIVE YOUNG VOC PRODUCT RESEARCH")
st.caption("Google Play 리뷰 3,000건 | GPT API 기반 AI 분석")
st.divider()

# ── 공통 필터 ─────────────────────────────────────────────────
st.markdown("### 🎛️ 분석 범위 설정")
st.caption(
    "기간 필터는 Impact Score 모집단을 결정합니다. "
    "대상/Severity 필터는 상세 탐색용이며 Impact Score와 독립적으로 작동합니다. "
    "(P1: 두 필터 분리 예정)"
)

fc1, fc2, fc3 = st.columns(3)

with fc1:
    period_opt = st.radio(
        "📅 분석 기간",
        ["최근 1년", "최근 2년", "최근 3년", "전체 기간"],
        index=1,
        horizontal=True
    )

with fc2:
    senti_opt = st.radio(
        "😡 대상",
        ["전체", "부정 VOC", "Critical", "Update Trigger"],
        index=0,
        horizontal=True
    )

with fc3:
    sev_opt = st.radio(
        "⚡ Severity",
        ["전체", "Critical", "High", "Medium", "Low"],
        index=0,
        horizontal=True
    )

# 기간 계산
period_map = {
    "최근 1년": pd.DateOffset(years=1),
    "최근 2년": pd.DateOffset(years=2),
    "최근 3년": pd.DateOffset(years=3),
}
start_date = (
    LATEST_DATE - period_map[period_opt]
    if period_opt != "전체 기간"
    else df_raw['at'].min()
)

# 기간 필터 적용 (Impact Score 모집단)
df_period = df_raw[df_raw['at'] >= start_date].copy()

# 대상/Severity 필터 (탐색용)
df = df_period.copy()
if senti_opt == "부정 VOC":
    df = df[df['sentiment'] == '부정']
elif senti_opt == "Critical":
    df = df[df['severity_label'] == 'Critical']
elif senti_opt == "Update Trigger":
    df = df[df['update_triggered'] == True]
if sev_opt != "전체":
    df = df[df['severity_label'] == sev_opt]

# P0⑥: Impact Score는 기간 필터만 적용한 데이터로 계산
impact = calc_impact_score(df_period)
neg_df = df_period[df_period['sentiment'] == '부정']

# 분석 범위 명시
st.info(
    f"📌 **분석 범위:** {start_date.date()} ~ {LATEST_DATE.date()} | "
    f"**{len(df_period):,}건** (부정 {len(neg_df):,}건) "
    + ("| 기본값: 최근 2년 — 장기 누적 VOC로 인한 현재성 저하를 줄이기 위해 설정"
       if period_opt == "최근 2년" else "")
)

st.divider()

# ── ① EXECUTIVE SUMMARY ──────────────────────────────────────
st.markdown("### 📊 EXECUTIVE SUMMARY")

c1, c2, c3, c4, c5 = st.columns(5)
neg_cnt  = len(neg_df)
crit_cnt = len(df_period[df_period['severity_label'] == 'Critical'])
upd_cnt  = int(df_period['update_triggered'].sum())
hconf    = len(df_period[df_period['confidence_level'] == '높음'])

with c1:
    st.metric("📋 분석 대상",
              f"{len(df_period):,}건",
              f"전체의 {len(df_period)/TOTAL_RAW*100:.1f}%")
with c2:
    st.metric("😡 부정 비율",
              f"{neg_cnt/len(df_period)*100:.1f}%" if len(df_period) > 0 else "0%",
              f"{neg_cnt:,}건")
with c3:
    st.metric("🚨 Critical",
              f"{crit_cnt:,}건",
              f"부정의 {crit_cnt/neg_cnt*100:.1f}%" if neg_cnt > 0 else "0%")
with c4:
    st.metric("🔄 Update Trigger",
              f"{upd_cnt:,}건",
              f"전체의 {upd_cnt/len(df_period)*100:.1f}%" if len(df_period) > 0 else "0%")
with c5:
    st.metric("🎯 High Confidence",
              f"{hconf:,}건",
              f"{hconf/len(df_period)*100:.1f}%" if len(df_period) > 0 else "0%")

st.divider()

# ── ② TOP PRIORITY ────────────────────────────────────────────
st.markdown("### 🔥 TOP PRIORITY ISSUES")

# P0①: Relative Impact Score 명시
# P0⑤: 가중치 설명 추가
st.caption(
    "**Relative Impact Score** — 선택 기간 내 부정 VOC 기준 상대적 우선순위 | "
    "심각도(Severity 50%) · 빈도(Frequency 30%) · AI 분석 신뢰도(Confidence 20%) | "
    "개선 검토 순서 탐색을 위한 휴리스틱 지표 (절대 점수 아님)"
)

if len(impact) > 0:
    top3 = impact.head(3)
    top3_cnt   = neg_df[neg_df['sub_category'].isin(top3['sub_category'])]
    top3_ratio = len(top3_cnt) / neg_cnt * 100 if neg_cnt > 0 else 0

    st.caption(
        f"부정 리뷰 {neg_cnt:,}건 중 상위 3개 카테고리 **{top3_ratio:.1f}%** 차지"
    )

    rank_emoji = ['①', '②', '③']
    cols = st.columns(3)
    for i, (_, row) in enumerate(top3.iterrows()):
        if i >= 3:
            break
        with cols[i]:
            st.markdown(f"**{rank_emoji[i]} {row['sub_category']}**")
            m1, m2, m3 = st.columns(3)
            m1.metric("Impact",   f"{row['impact_score']:.0f}")
            m2.metric("VOC",      f"{row['neg_count']:,}건")
            m3.metric("Severity", f"{row['avg_severity']:.1f}")
            st.info(f"💡 {row['top_product_insight']}")

    st.markdown("---")

    # Priority Matrix
    st.markdown(
        "**📊 PRIORITY MATRIX** — VOC 규모와 Relative Impact Score를 함께 비교하여 "
        "개선 우선순위 탐색 (두 축이 일부 요소를 공유할 수 있음)"
    )

    mid_x = impact['neg_count'].median()
    mid_y = impact['impact_score'].median()

    fig_matrix = px.scatter(
        impact,
        x='neg_count',
        y='impact_score',
        size='avg_severity',
        color='impact_score',
        color_continuous_scale=['#FFF3E0', '#FF6F00'],
        text='sub_category',
        labels={
            'neg_count':    'VOC Volume (부정 건수)',
            'impact_score': 'Relative Impact Score',
            'avg_severity': 'Avg Severity'
        },
        size_max=40,
        hover_data={
            'neg_count':       True,
            'avg_severity':    True,
            'frequency_ratio': True,
            'conf_ratio':      True,
            'impact_score':    True
        }
    )
    fig_matrix.update_traces(
        textposition='top center',
        textfont_size=11
    )
    fig_matrix.update_layout(
        height=400,
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=10, b=10)
    )
    fig_matrix.add_hline(
        y=mid_y, line_dash='dot', line_color='gray', opacity=0.4
    )
    fig_matrix.add_vline(
        x=mid_x, line_dash='dot', line_color='gray', opacity=0.4
    )
    x_max = impact['neg_count'].max()
    y_max = impact['impact_score'].max()
    fig_matrix.update_layout(annotations=[
        dict(x=x_max*0.88, y=y_max*0.97,
             text="🔴 핵심 개선 검토",     showarrow=False,
             font=dict(size=10, color='red')),
        dict(x=mid_x*0.15, y=y_max*0.97,
             text="🟠 심각도 중심 검토",   showarrow=False,
             font=dict(size=10, color='orange')),
        dict(x=x_max*0.88, y=mid_y*0.3,
             text="🟡 반복 이슈 모니터링", showarrow=False,
             font=dict(size=10, color='goldenrod')),
        dict(x=mid_x*0.15, y=mid_y*0.3,
             text="⬜ 관찰 영역",          showarrow=False,
             font=dict(size=10, color='gray')),
    ])
    st.plotly_chart(fig_matrix, use_container_width=True)

else:
    st.warning("선택한 조건에 해당하는 데이터가 없어요.")

st.divider()

# ── ③ USER JOURNEY ────────────────────────────────────────────
st.markdown("### 🧭 USER JOURNEY")
st.caption("고객이 어느 여정 단계에서 어떤 문제를 겪고 있는가")

JOURNEY_ORDER = ['탐색', '상품선택', '구매/결제', '배송', '사후관리']

# B. 플로우 방식
st.markdown("**▸ 여정별 부정 리뷰 집중도**")

if neg_cnt > 0:
    j_counts = (
        neg_df['user_journey_stage']
        .value_counts()
        .reindex(JOURNEY_ORDER)
        .fillna(0)
        .astype(int)
    )
    max_cnt = j_counts.max()

    flow_cols = st.columns(len(JOURNEY_ORDER) * 2 - 1)
    for i, stage in enumerate(JOURNEY_ORDER):
        count     = j_counts[stage]
        ratio     = count / neg_cnt * 100
        intensity = count / max_cnt if max_cnt > 0 else 0

        color = "#B71C1C" if intensity >= 0.7 else (
            "#EF5350" if intensity >= 0.4 else "#FFCDD2"
        )
        label = "❗ 높음" if intensity >= 0.7 else (
            "⚠️ 중간" if intensity >= 0.4 else "✅ 낮음"
        )

        with flow_cols[i * 2]:
            st.markdown(
                f"<div style='background:{color};border-radius:10px;"
                f"padding:12px 8px;text-align:center;color:white;font-weight:bold;'>"
                f"<div style='font-size:13px'>{stage}</div>"
                f"<div style='font-size:18px;margin:4px 0'>{count:,}건</div>"
                f"<div style='font-size:11px'>{ratio:.1f}%</div>"
                f"<div style='font-size:11px'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        if i < len(JOURNEY_ORDER) - 1:
            with flow_cols[i * 2 + 1]:
                st.markdown(
                    "<div style='text-align:center;font-size:20px;"
                    "padding-top:20px'>→</div>",
                    unsafe_allow_html=True
                )

st.markdown("<br>", unsafe_allow_html=True)

# A-1. Category × Journey (메인)
st.markdown("**▸ Category × Journey** — 어떤 여정에서 어떤 문제가 발생하는가")

if neg_cnt > 0:
    top5_cats = neg_df['sub_category'].value_counts().head(5).index.tolist()
    cj_df = neg_df[neg_df['sub_category'].isin(top5_cats)]
    cat_journey = pd.crosstab(
        cj_df['sub_category'],
        cj_df['user_journey_stage']
    ).reindex(columns=JOURNEY_ORDER, fill_value=0)

    fig_cj = px.imshow(
        cat_journey,
        labels=dict(x="Journey Stage", y="Category", color="건수"),
        color_continuous_scale=['#FFF9C4', '#B71C1C'],
        text_auto=True,
        aspect='auto'
    )
    fig_cj.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_cj, use_container_width=True)

# A-2. Journey × Severity (보조)
st.markdown("**▸ Journey × Severity** — 단계별 문제 심각도")

if neg_cnt > 0:
    SEV_ORDER = ['Critical', 'High', 'Medium', 'Low']
    cross = pd.crosstab(
        neg_df['user_journey_stage'],
        neg_df['severity_label']
    ).reindex(index=JOURNEY_ORDER, columns=SEV_ORDER, fill_value=0)

    fig_heat = px.imshow(
        cross,
        labels=dict(x="Severity", y="Journey Stage", color="건수"),
        color_continuous_scale=['#FFF9C4', '#B71C1C'],
        text_auto=True,
        aspect='auto'
    )
    fig_heat.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_heat, use_container_width=True)

st.divider()

# ── ④ ROOT CAUSE HYPOTHESIS ──────────────────────────────────
st.markdown("### 🔎 원인 추정 (Root Cause Hypothesis)")
st.caption(
    "리뷰 텍스트 기반 GPT 추정 결과 — 실제 원인이 아닌 가설이며 "
    "서버 로그 등 추가 검증이 필요합니다."
)

if len(impact) > 0:
    rc_cat = st.selectbox("카테고리 선택", impact['sub_category'].tolist(), key='rc')
    rc_df  = neg_df[neg_df['sub_category'] == rc_cat]

    rc_col, pi_col = st.columns(2)
    with rc_col:
        st.markdown("**원인 추정 패턴**")
        for _, row in (
            rc_df['root_causes'].dropna()
            .value_counts().head(5)
            .reset_index()
            .rename(columns={'root_causes': '원인', 'count': '건수'})
            .iterrows()
        ):
            st.markdown(f"- {row['원인']} `{row['건수']}건`")

    with pi_col:
        st.markdown("**Product Insight**")
        for _, row in (
            rc_df['product_insight'].dropna()
            .value_counts().head(5)
            .reset_index()
            .rename(columns={'product_insight': 'insight', 'count': '건수'})
            .iterrows()
        ):
            st.markdown(f"- {row['insight']} `{row['건수']}건`")

st.divider()

# ── ⑤ IMPROVEMENT OPPORTUNITY ────────────────────────────────
st.markdown("### 💡 IMPROVEMENT OPPORTUNITY")
st.caption("Pain Point → Recommendation → Expected KPI")

if len(impact) > 0:
    imp_cat = st.selectbox(
        "카테고리 선택", impact['sub_category'].tolist(), key='imp'
    )
    imp_df = neg_df[neg_df['sub_category'] == imp_cat]

    i1, i2, i3 = st.columns(3)
    with i1:
        st.markdown("**😣 Pain Point**")
        for _, row in (
            imp_df['summary'].dropna()
            .value_counts().head(5)
            .reset_index()
            .rename(columns={'summary': 'pain', 'count': 'cnt'})
            .iterrows()
        ):
            st.markdown(f"- {row['pain']} `{row['cnt']}건`")

    with i2:
        st.markdown("**🔧 Recommendation**")
        for _, row in (
            imp_df['recommendation'].dropna()
            .value_counts().head(5)
            .reset_index()
            .rename(columns={'recommendation': 'rec', 'count': 'cnt'})
            .iterrows()
        ):
            st.markdown(f"- {row['rec']} `{row['cnt']}건`")

    with i3:
        st.markdown("**📈 Expected KPI**")
        kpi_counts = (
            imp_df['expected_kpi'].dropna()
            .value_counts().head(5)
            .reset_index()
            .rename(columns={'expected_kpi': 'kpi', 'count': 'cnt'})
        )
        for _, row in kpi_counts.iterrows():
            direction = imp_df[
                imp_df['expected_kpi'] == row['kpi']
            ]['expected_kpi_direction'].mode()
            arrow = "▼" if (
                len(direction) > 0 and direction.iloc[0] == '감소'
            ) else "▲"
            st.markdown(f"- {arrow} {row['kpi']} `{row['cnt']}건`")

st.divider()

# ── ⑥ RAW VOC ────────────────────────────────────────────────
st.markdown("### 📝 RAW VOC")
st.caption(
    "실제 고객 리뷰 + AI 분석 결과 | 상위 200건 표시 | "
    "상단 필터(기간·대상·Severity)가 이미 적용된 상태입니다."
)

# P0③: RAW VOC 중복 필터 제거 → 카테고리만 유지
cat_f = st.selectbox(
    "카테고리 필터",
    ['전체'] + sorted(df['sub_category'].dropna().unique().tolist()),
    key='voc_cat'
)

filtered = df.copy()
if cat_f != '전체':
    filtered = filtered[filtered['sub_category'] == cat_f]

st.caption(f"📌 조회 결과: {len(filtered):,}건")

display_cols = [
    'content', 'sentiment', 'sub_category', 'severity_label',
    'user_journey_stage', 'root_causes', 'product_insight',
    'recommendation', 'expected_kpi', 'summary', 'confidence_score'
]
col_rename = {
    'content':            '리뷰 원문',
    'sentiment':          '감성',
    'sub_category':       '카테고리',
    'severity_label':     'Severity',
    'user_journey_stage': 'Journey Stage',
    'root_causes':        '원인 추정',
    'product_insight':    'Product Insight',
    'recommendation':     '개선 제언',
    'expected_kpi':       'KPI',
    'summary':            '요약',
    'confidence_score':   'Confidence'
}
st.dataframe(
    filtered[display_cols].rename(columns=col_rename).head(200),
    use_container_width=True,
    height=400,
    column_config={
        '리뷰 원문':    st.column_config.TextColumn(width='large'),
        'Confidence': st.column_config.ProgressColumn(
            min_value=0, max_value=1, format='%.2f'
        )
    }
)

# CSV 다운로드
csv_data = (
    filtered[display_cols]
    .rename(columns=col_rename)
    .to_csv(index=False)
    .encode('utf-8-sig')
)
st.download_button(
    label="📥 필터링된 VOC 다운로드 (CSV)",
    data=csv_data,
    file_name=f"oliveyoung_voc_{period_opt.replace(' ','_')}.csv",
    mime="text/csv"
)

# ── 푸터 ─────────────────────────────────────────────────────
st.divider()
st.caption(
    "📌 올리브영 앱 Google Play 리뷰 기반 Product Research 프로젝트 | "
    "CSV 기반 구조이며 DB 연동 시 확장 가능 (연동 시 캐시/갱신 전략 별도 필요)"
)
st.caption(
    "⚠️ 한계: "
    "① confidence 낮음+매우낮음(185건, 6.2%) 포함 "
    "② 구글 플레이 리뷰 특성상 부정 편향 존재 "
    "③ Root Cause는 GPT 텍스트 추정이며 실제 원인 검증 필요 "
    "④ Relative Impact Score는 선택 기간 내 상대 비교 점수"
)