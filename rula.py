import streamlit as st
from openai import OpenAI
import datetime

# ===================== 页面基础配置 =====================
st.set_page_config(
    page_title="RULA快速上肢评估系统",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 页面样式优化
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #0070C0;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .section-header {
        background-color: #D9E1F2;
        padding: 10px;
        border-radius: 5px;
        margin: 15px 0;
        font-weight: bold;
        color: #003366;
    }
    .score-box {
        background-color: #F0F2F6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin: 10px 0;
    }
    .score-value {
        font-size: 28px;
        font-weight: bold;
        color: #0070C0;
    }
    .risk-high {
        color: #C00000;
        font-weight: bold;
    }
    .risk-medium {
        color: #ED7D31;
        font-weight: bold;
    }
    .risk-low {
        color: #00B050;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ===================== 初始化会话状态 =====================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "client" not in st.session_state:
    st.session_state.client = None
if "api_key_entered" not in st.session_state:
    st.session_state.api_key_entered = False
if "rula_result" not in st.session_state:
    st.session_state.rula_result = None

# ===================== RULA评分核心逻辑 =====================
# 1. 手臂弯曲评分
def get_arm_score(arm_angle, arm_abduction, shoulder_raise, arm_support):
    base_score = 1
    if 20 < arm_angle <= 45 or arm_angle < -20:
        base_score = 2
    elif 45 < arm_angle <= 90:
        base_score = 3
    elif arm_angle > 90:
        base_score = 4
    
    # 增加分值
    add_score = 0
    if arm_abduction:
        add_score += 1
    if shoulder_raise:
        add_score += 1
    if arm_support:
        add_score -= 1
    
    final_score = max(1, base_score + add_score)
    return final_score

# 2. 前臂弯曲评分
def get_forearm_score(forearm_angle, forearm_abduction):
    base_score = 1
    if forearm_angle < 60 or forearm_angle > 100:
        base_score = 2
    
    add_score = 1 if forearm_abduction else 0
    final_score = max(1, base_score + add_score)
    return final_score

# 3. 手腕评分
def get_wrist_score(wrist_bend, wrist_twist):
    base_score = 1
    if 0 < abs(wrist_bend) <= 15:
        base_score = 2
    elif abs(wrist_bend) > 15:
        base_score = 3
    
    add_score = 1 if wrist_twist else 0
    final_score = max(1, base_score + add_score)
    return final_score

# 4. 颈部评分
def get_neck_score(neck_angle, neck_twist, neck_bend):
    base_score = 1
    if 10 < neck_angle <= 20:
        base_score = 2
    elif neck_angle > 20:
        base_score = 3
    elif neck_angle < 0:
        base_score = 4
    
    add_score = 0
    if neck_twist:
        add_score += 1
    if neck_bend:
        add_score += 1
    
    final_score = max(1, base_score + add_score)
    return final_score

# 5. 身躯评分
def get_trunk_score(trunk_angle, trunk_twist, trunk_bend):
    base_score = 1
    if 0 < trunk_angle <= 20:
        base_score = 2
    elif 20 < trunk_angle <= 60:
        base_score = 3
    elif trunk_angle > 60:
        base_score = 4
    
    add_score = 0
    if trunk_twist:
        add_score += 1
    if trunk_bend:
        add_score += 1
    
    final_score = max(1, base_score + add_score)
    return final_score

# 6. 腿部评分
def get_leg_score(leg_support):
    return 1 if leg_support else 2

# 7. 肌肉状态评分
def get_muscle_score(muscle_state):
    if muscle_state == "静态持物超过1分钟":
        return 1
    elif muscle_state == "重复作业超过4次/分钟":
        return 1
    else:
        return 0

# 8. 力量负荷评分
def get_load_score(load_state):
    if load_state == "无作用力/小于2kg":
        return 0
    elif load_state == "2-10kg周期性负荷":
        return 1
    elif load_state == "2-10kg静态/重复负荷":
        return 2
    elif load_state == "10kg以上静态/重复负荷":
        return 3
    else:
        return 0

# 9. A总分计算
def calculate_a_total(arm_score, forearm_score, wrist_score):
    return arm_score + forearm_score + wrist_score

# 10. B总分计算
def calculate_b_total(neck_score, trunk_score, leg_score):
    return neck_score + trunk_score + leg_score

# 11. C/D总分计算
def calculate_cd_total(base_total, muscle_score, load_score):
    return base_total + muscle_score + load_score

# 12. 最终RULA总分查表
def get_rula_total(c_total, d_total):
    # RULA总分对照表（完全匹配你提供的Excel表）
    rula_table = [
        [1, 2, 3, 3, 4, 5, 5, 6, 7],
        [2, 2, 3, 4, 4, 5, 6, 6, 7],
        [3, 3, 3, 4, 5, 5, 6, 7, 7],
        [3, 4, 4, 5, 5, 6, 6, 7, 7],
        [4, 4, 5, 5, 6, 6, 7, 7, 7],
        [5, 5, 5, 6, 6, 7, 7, 7, 7],
        [5, 6, 6, 6, 7, 7, 7, 7, 7],
        [6, 6, 7, 7, 7, 7, 7, 7, 7],
        [7, 7, 7, 7, 7, 7, 7, 7, 7]
    ]
    # 索引从0开始，所以减1
    c_idx = max(0, min(8, c_total - 1))
    d_idx = max(0, min(8, d_total - 1))
    return rula_table[c_idx][d_idx]

# 13. 行动水准和处理方案
def get_action_level(rula_total):
    if 1 <= rula_total <= 2:
        return "AL1", "不需处理", "risk-low"
    elif 3 <= rula_total <= 4:
        return "AL2", "进一步调查及必要时进行改善", "risk-medium"
    elif 5 <= rula_total <= 6:
        return "AL3", "近日内需进行进一步调查及改善", "risk-medium"
    elif rula_total == 7:
        return "AL4", "必须立即进行调查及改善", "risk-high"
    else:
        return "未知", "无效评分", ""

# ===================== SiliconFlow DeepSeek API 调用（和疲劳工具完全统一） =====================
def call_deepseek_api(messages):
    try:
        if not st.session_state.client:
            # 直接复用你之前疲劳工具的 API_KEY，不用改 Secrets 配置
            try:
                API_KEY = st.secrets["API_KEY"]
                st.session_state.client = OpenAI(api_key=API_KEY, base_url="https://api.siliconflow.cn/v1")
                st.session_state.api_key_entered = True
            except Exception as e:
                st.error(f"API 初始化失败：{str(e)}")
                st.info("请确保已在 Streamlit Secrets 中配置了 API_KEY")
                return None
        
        completion = st.session_state.client.chat.completions.create(
            model="Pro/deepseek-ai/DeepSeek-V3.2",  # 和疲劳工具同一个模型
            messages=messages,
            stream=True
        )
        response = ""
        for chunk in completion:
            if chunk.choices and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                if hasattr(choice, "delta") and hasattr(choice.delta, "content") and choice.delta.content is not None:
                    response += choice.delta.content
        return response
    except Exception as e:
        st.error(f"API调用错误: {str(e)}")
        return None

# ===================== 主页面内容 =====================
# 标题
st.markdown("<h1 class='main-header'>RULA快速上肢评估系统</h1>", unsafe_allow_html=True)
st.markdown("本系统依据国际标准ISO 11226，对工作过程中的上肢疲劳状态进行科学评估，自动计算评分并给出专业改善建议。")

# 评估表单
with st.form("rula_assessment_form"):
    # A部分：手臂、前臂、手腕评分
    st.markdown("<div class='section-header'>一、A部分：上肢评分（手臂、前臂、手腕）</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 1）手臂弯曲评分")
        arm_angle = st.slider("手臂弯曲角度（°）", -90, 180, 0, help="前倾为正，后倾为负")
        arm_abduction = st.checkbox("手臂外扩", value=False)
        shoulder_raise = st.checkbox("肩膀提高", value=False)
        arm_support = st.checkbox("手臂有支撑", value=False)
        arm_score = get_arm_score(arm_angle, arm_abduction, shoulder_raise, arm_support)
        st.metric("手臂最终评分", arm_score)
    
    with col2:
        st.markdown("#### 2）前臂弯曲评分")
        forearm_angle = st.slider("前臂弯曲角度（°）", 0, 180, 90, help="60-100°为中立位")
        forearm_abduction = st.checkbox("前臂外扩", value=False)
        forearm_score = get_forearm_score(forearm_angle, forearm_abduction)
        st.metric("前臂最终评分", forearm_score)
    
    with col3:
        st.markdown("#### 3）手腕评分")
        wrist_bend = st.slider("手腕弯曲角度（°）", -45, 45, 0, help="上倾为正，下倾为负")
        wrist_twist = st.checkbox("手腕扭转", value=False)
        wrist_score = get_wrist_score(wrist_bend, wrist_twist)
        st.metric("手腕最终评分", wrist_score)
    
    # B部分：颈部、身躯、腿部评分
    st.markdown("<div class='section-header'>二、B部分：躯干评分（颈部、身躯、腿部）</div>", unsafe_allow_html=True)
    
    col4, col5, col6 = st.columns(3)
    with col4:
        st.markdown("#### 1）颈部评分")
        neck_angle = st.slider("颈部弯曲角度（°）", -30, 60, 0, help="前倾为正，后仰为负")
        neck_twist = st.checkbox("颈部扭转", value=False)
        neck_bend = st.checkbox("颈部侧弯", value=False)
        neck_score = get_neck_score(neck_angle, neck_twist, neck_bend)
        st.metric("颈部最终评分", neck_score)
    
    with col5:
        st.markdown("#### 2）身躯评分")
        trunk_angle = st.slider("身躯弯曲角度（°）", 0, 90, 0, help="前倾为正")
        trunk_twist = st.checkbox("身躯扭转", value=False)
        trunk_bend = st.checkbox("身躯侧弯", value=False)
        trunk_score = get_trunk_score(trunk_angle, trunk_twist, trunk_bend)
        st.metric("身躯最终评分", trunk_score)
    
    with col6:
        st.markdown("#### 3）腿部评分")
        leg_support = st.checkbox("腿和脚踝有适当支撑且平衡", value=True)
        leg_score = get_leg_score(leg_support)
        st.metric("腿部最终评分", leg_score)
    
    # C/D部分：肌肉、负荷评分
    st.markdown("<div class='section-header'>三、C/D部分：肌肉与负荷评分</div>", unsafe_allow_html=True)
    
    col7, col8 = st.columns(2)
    with col7:
        st.markdown("#### 1）肌肉状态评分")
        muscle_state = st.selectbox(
            "肌肉工作状态",
            ["无特殊状态", "静态持物超过1分钟", "重复作业超过4次/分钟"],
            index=0
        )
        muscle_score = get_muscle_score(muscle_state)
        st.metric("肌肉状态评分", muscle_score)
    
    with col8:
        st.markdown("#### 2）力量负荷评分")
        load_state = st.selectbox(
            "工作负荷状态",
            ["无作用力/小于2kg", "2-10kg周期性负荷", "2-10kg静态/重复负荷", "10kg以上静态/重复负荷"],
            index=0
        )
        load_score = get_load_score(load_state)
        st.metric("力量负荷评分", load_score)
    
    # 提交按钮
    submit_button = st.form_submit_button("开始评估", type="primary", use_container_width=True)

# 评估结果计算与展示
if submit_button:
    # 计算各项总分
    a_total = calculate_a_total(arm_score, forearm_score, wrist_score)
    b_total = calculate_b_total(neck_score, trunk_score, leg_score)
    c_total = calculate_cd_total(a_total, muscle_score, load_score)
    d_total = calculate_cd_total(b_total, muscle_score, load_score)
    rula_total = get_rula_total(c_total, d_total)
    action_level, action_plan, risk_class = get_action_level(rula_total)
    
    # 保存结果到会话状态
    st.session_state.rula_result = {
        "a_total": a_total,
        "b_total": b_total,
        "c_total": c_total,
        "d_total": d_total,
        "rula_total": rula_total,
        "action_level": action_level,
        "action_plan": action_plan,
        "risk_class": risk_class,
        "assessment_data": {
            "arm_angle": arm_angle,
            "forearm_angle": forearm_angle,
            "wrist_bend": wrist_bend,
            "neck_angle": neck_angle,
            "trunk_angle": trunk_angle,
            "muscle_state": muscle_state,
            "load_state": load_state
        }
    }
    
    # 展示评分结果
    st.markdown("<div class='section-header'>四、评估结果</div>", unsafe_allow_html=True)
    
    col9, col10, col11, col12 = st.columns(4)
    with col9:
        st.markdown("<div class='score-box'>", unsafe_allow_html=True)
        st.markdown("A总分（上肢）")
        st.markdown(f"<div class='score-value'>{a_total}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col10:
        st.markdown("<div class='score-box'>", unsafe_allow_html=True)
        st.markdown("B总分（躯干）")
        st.markdown(f"<div class='score-value'>{b_total}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col11:
        st.markdown("<div class='score-box'>", unsafe_allow_html=True)
        st.markdown("C/D总分")
        st.markdown(f"<div class='score-value'>{c_total}/{d_total}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col12:
        st.markdown("<div class='score-box'>", unsafe_allow_html=True)
        st.markdown("最终RULA总分")
        st.markdown(f"<div class='score-value {risk_class}'>{rula_total}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    # 行动水准
    st.markdown(f"""
    <div style='background-color: #F8F9FA; padding: 20px; border-radius: 10px; margin: 15px 0;'>
        <h3>行动水准：<span class='{risk_class}'>{action_level}</span></h3>
        <p>处理方案：<span class='{risk_class}'>{action_plan}</span></p>
    </div>
    """, unsafe_allow_html=True)
    
    # 自动生成AI分析
    st.markdown("<div class='section-header'>五、AI专业分析与改善建议</div>", unsafe_allow_html=True)
    with st.spinner("正在生成专业分析..."):
        # 构建AI提示词
        ai_prompt = f"""
        你是专业的人因工程专家，精通ISO 11226标准和RULA快速上肢评估方法。
        以下是用户的RULA评估数据，请基于这些数据进行专业的风险分析，并给出可落地的改善建议。

        评估数据：
        1. 上肢评分：
           - 手臂弯曲角度：{arm_angle}°，评分：{arm_score}
           - 前臂弯曲角度：{forearm_angle}°，评分：{forearm_score}
           - 手腕弯曲角度：{wrist_bend}°，评分：{wrist_score}
           - A总分：{a_total}
        2. 躯干评分：
           - 颈部弯曲角度：{neck_angle}°，评分：{neck_score}
           - 身躯弯曲角度：{trunk_angle}°，评分：{trunk_score}
           - 腿部评分：{leg_score}
           - B总分：{b_total}
        3. 肌肉与负荷评分：
           - 肌肉状态：{muscle_state}，评分：{muscle_score}
           - 负荷状态：{load_state}，评分：{load_score}
           - C总分：{c_total}，D总分：{d_total}
        4. 最终结果：
           - RULA总分：{rula_total}
           - 行动水准：{action_level}
           - 处理方案：{action_plan}

        要求：
        1. 先说明整体的风险等级和核心问题
        2. 分点分析每个身体部位的具体风险，结合ISO 11226标准
        3. 给出针对性的、可落地的改善建议，分为姿势调整、工作环境优化、休息方案三个部分
        4. 语言专业、简洁、易懂，避免太学术化的术语
        """
        
        # 调用AI
        ai_response = call_deepseek_api([
            {"role": "system", "content": "你是专业的人因工程专家，精通ISO 11226标准和RULA快速上肢评估方法。"},
            {"role": "user", "content": ai_prompt}
        ])
        
        if ai_response:
            st.session_state.messages = [
                {"role": "system", "content": "你是专业的人因工程专家，精通ISO 11226标准和RULA快速上肢评估方法。"},
                {"role": "user", "content": ai_prompt},
                {"role": "assistant", "content": ai_response}
            ]
            st.markdown(ai_response)

# 持续对话交流
st.markdown("<div class='section-header'>六、持续咨询交流</div>", unsafe_allow_html=True)

# 显示聊天记录
def display_chat_messages():
    if "messages" in st.session_state:
        for msg in st.session_state.messages:
            if msg["role"] != "system":
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

display_chat_messages()

# 聊天输入框
prompt = st.chat_input("继续咨询人因工程相关问题：")
if prompt:
    if not st.session_state.api_key_entered:
        st.error("请先完成评估，系统会自动初始化API")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.spinner("思考中..."):
            full_response = call_deepseek_api(st.session_state.messages)
            if full_response:
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.rerun()

# 侧边栏说明
with st.sidebar:
    st.markdown("### 系统说明")
    st.markdown("""
    本系统基于**RULA快速上肢评估法**和**ISO 11226国际标准**开发，用于评估工作过程中的上肢肌肉骨骼疲劳风险。
    
    #### 核心功能：
    1. 标准化的RULA评分计算
    2. 自动匹配风险等级和行动方案
    3. AI专业分析与改善建议
    4. 持续的人因工程咨询交流
    
    #### 使用方法：
    1. 填写所有评估项，点击「开始评估」
    2. 查看自动计算的评分结果和风险等级
    3. 阅读AI生成的专业分析和改善建议
    4. 可在底部继续咨询相关问题
    """)
    
    st.markdown("### 评分标准说明")
    st.markdown("""
    | RULA总分 | 行动水准 | 处理方案 |
    |----------|----------|----------|
    | 1-2 | AL1 | 不需处理 |
    | 3-4 | AL2 | 进一步调查及必要时改善 |
    | 5-6 | AL3 | 近日内需进一步调查及改善 |
    | 7 | AL4 | 必须立即调查及改善 |
    """)
