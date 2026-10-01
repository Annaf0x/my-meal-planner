import html
import re
import pandas as pd
import streamlit as st

# ==================== 1. 页面基本配置 ====================
st.set_page_config(
    page_title="单人高蛋白减脂菜谱与智能采购助手",
    page_icon="🥗",
    layout="wide",
)


# ==================== 2. 数据加载函数 ====================
@st.cache_data
def load_data():
    file_path = "recipes_for_notion_cn_cleaned.csv"
    try:
        df = pd.read_csv(file_path, encoding="utf-8-sig")
    except Exception:
        # 兼容性处理
        df = pd.read_csv(file_path, encoding="gbk", errors="ignore")

    # 填充空值
    df["title"] = df["title"].fillna("未命名菜谱")
    df["ingredients"] = df["ingredients"].fillna("")
    df["instructions"] = df["instructions"].fillna("暂无详细步骤")
    df["prep_time"] = df["prep_time"].fillna("15-20 分钟")
    return df


df_recipes = load_data()

# ==================== 3. 页面标题与侧边栏（冰箱库存） ====================
st.title("🥗 单人高蛋白减脂菜谱 & 智能采购助手")
st.caption("自动规划伙食 | 匹配冰箱现有食材 | 生成无刷新勾选清单")

st.sidebar.header("🧊 冰箱现有库存 (Fridge Pantry)")
st.sidebar.write("勾选或输入你冰箱里已有的食材，采购清单会自动帮你扣除：")

# 常见基础调味料/食材，默认勾选
default_pantry = ["盐", "黑胡椒", "食用油", "大蒜", "酱油", "水"]
user_pantry_input = st.sidebar.text_area(
    "输入其他现有食材（用逗号或换行隔开）：",
    value="鸡蛋, 鸡胸肉, 橄榄油",
    help="例如：大蒜, 鸡蛋, 西兰花",
)

# 解析用户冰箱库存列表
custom_pantry = [
    item.strip()
    for item in re.split(r"[,，\n]", user_pantry_input)
    if item.strip()
]
all_pantry = list(set(default_pantry + custom_pantry))

st.sidebar.success(f"已识别冰箱食材 {len(all_pantry)} 种")

# ==================== 4. 菜谱筛选与选择 ====================
st.header("🍱 第一步：选择本周想吃的减脂菜谱")

search_term = st.text_input("🔍 搜索菜谱或食材（如：鸡肉、牛肉、虾、沙拉）：", "")

if search_term:
    filtered_df = df_recipes[
        df_recipes["title"].str.contains(search_term, case=False, na=False)
        | df_recipes["ingredients"].str.contains(
            search_term, case=False, na=False
        )
    ]
else:
    filtered_df = df_recipes

# 供用户多选菜谱
selected_titles = st.multiselect(
    "勾选你要加入本周菜单的菜谱（可多选）：",
    options=filtered_df["title"].tolist(),
    default=(
        filtered_df["title"].tolist()[:3]
        if len(filtered_df) >= 3
        else filtered_df["title"].tolist()
    ),
)

# 展示选中菜谱的详情
if selected_titles:
    st.markdown("### 📖 已选菜谱预览")
    cols = st.columns(min(len(selected_titles), 3))
    selected_rows = df_recipes[df_recipes["title"].isin(selected_titles)]

    for idx, (_, row) in enumerate(selected_rows.iterrows()):
        with cols[idx % 3]:
            st.info(f"**{row['title']}**")
            st.caption(f"⏱ 准备时间：{row['prep_time']}")
            with st.expander("查看烹饪步骤与食材"):
                st.write("**食材列表：**")
                st.write(row["ingredients"])
                st.write("**制作步骤：**")
                st.write(row["instructions"])

# ==================== 5. 智能计算与合并采购清单 ====================
st.divider()
st.header("🛒 第二步：智能合并采购清单")


def parse_and_merge_ingredients(selected_rows, pantry_list):
    """解析食材，合并同类项，并自动扣除冰箱已有食材"""
    raw_ingredients = []

    for _, row in selected_rows.iterrows():
        ing_text = str(row["ingredients"])
        # 处理按 '|' 或换行分隔的食材
        items = re.split(r"[|\n]", ing_text)
        for item in items:
            cleaned = item.strip().strip("•").strip()
            if cleaned:
                raw_ingredients.append(cleaned)

    # 去重与扣除冰箱库存
    shopping_items = []
    for item in raw_ingredients:
        # 判断是否在冰箱已有库存中
        is_in_pantry = any(p.lower() in item.lower() for p in pantry_list if p)
        if not is_in_pantry:
            shopping_items.append(item)

    # 合并完全相同的食材项
    item_counts = {}
    for item in shopping_items:
        item_counts[item] = item_counts.get(item, 0) + 1

    final_list = []
    for item, count in item_counts.items():
        display_text = f"{item} (x{count} 份量)" if count > 1 else item
        final_list.append({"完成": False, "食材项": display_text})

    return final_list


if selected_titles:
    selected_rows = df_recipes[df_recipes["title"].isin(selected_titles)]
    shopping_data = parse_and_merge_ingredients(selected_rows, all_pantry)

    if shopping_data:
        st.write("已为你整合所有所需食材，并**自动扣除**了冰箱已有的食材：")

        # 使用 DataFrame 搭配 st.data_editor 呈现无刷新勾选框
        df_shopping = pd.DataFrame(shopping_data)

        edited_df = st.data_editor(
            df_shopping,
            column_config={
                "完成": st.column_config.CheckboxColumn(
                    "已买/已有",
                    help="点击勾选，标注已购买",
                    default=False,
                ),
                "食材项": st.column_config.TextColumn(
                    "采购项目 (含剂量)", disabled=True
                ),
            },
            disabled=["食材项"],
            hide_index=True,
            use_container_width=True,
            key="shopping_list_editor",
        )

        # 采购进度统计
        total_count = len(edited_df)
        done_count = edited_df["完成"].sum()

        st.progress(done_count / total_count if total_count > 0 else 0)
        st.caption(f"📊 采购进度：{done_count} / {total_count}")

        if done_count == total_count and total_count > 0:
            st.balloons()
            st.success("🎉 太棒了！本周所有食材已全部备齐，可以开始大展身手了！")
    else:
        st.success("🎉 调取结果：所选菜谱需要的食材你冰箱里全部都有，无需采购！")
else:
    st.warning("👈 请先在上方勾选至少一道菜谱，系统将自动为你生成采购清单。")