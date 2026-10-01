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
        df = pd.read_csv(file_path, encoding="gbk", errors="ignore")

    df["title"] = df["title"].fillna("未命名菜谱")
    df["ingredients"] = df["ingredients"].fillna("")
    df["instructions"] = df["instructions"].fillna("暂无详细步骤")
    df["prep_time"] = df["prep_time"].fillna("15-20 分钟")
    if "image" not in df.columns:
        df["image"] = ""
    else:
        df["image"] = df["image"].fillna("")
    return df


df_recipes = load_data()

# ==================== 3. 页面标题与侧边栏（冰箱库存） ====================
st.title("🥗 单人高蛋白减脂菜谱 & 智能采购助手")
st.caption("批量餐数规划 | 匹配冰箱现有食材 | 自动生成无刷新合并采购清单")

st.sidebar.header("🧊 冰箱现有库存 (Fridge Pantry)")
st.sidebar.write("勾选或输入你冰箱里已有的食材，采购清单会自动扣除：")

default_pantry = ["盐", "黑胡椒", "食用油", "大蒜", "酱油", "水"]
user_pantry_input = st.sidebar.text_area(
    "输入其他现有食材（用逗号或换行隔开）：",
    value="鸡蛋, 鸡胸肉, 橄榄油",
    help="例如：大蒜, 鸡蛋, 西兰花",
)

custom_pantry = [
    item.strip()
    for item in re.split(r"[,，\n]", user_pantry_input)
    if item.strip()
]
all_pantry = list(set(default_pantry + custom_pantry))

st.sidebar.success(f"已识别冰箱食材 {len(all_pantry)} 种")

# ==================== 4. 菜谱筛选与餐数设置 ====================
st.header("🍱 第一步：选择菜谱并指定餐数（如：午餐做 4 顿相同的）")

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

selected_titles = st.multiselect(
    "勾选你要加入本周菜单的菜谱：",
    options=filtered_df["title"].tolist(),
    default=(
        filtered_df["title"].tolist()[:3]
        if len(filtered_df) >= 3
        else filtered_df["title"].tolist()
    ),
)

# 记录每道菜要吃几顿（份数乘数）
recipe_portions = {}

if selected_titles:
    st.markdown("### 📖 已选菜谱预览与餐数规划")
    selected_rows = df_recipes[df_recipes["title"].isin(selected_titles)]

    cols = st.columns(min(len(selected_titles), 3))

    for idx, (_, row) in enumerate(selected_rows.iterrows()):
        title = row["title"]
        with cols[idx % 3]:
            # 展示菜谱图片
            if row["image"] and str(row["image"]).startswith("http"):
                st.image(row["image"], use_container_width=True)
            else:
                st.info("🖼 暂无图片")

            st.subheader(title)
            st.caption(f"⏱ 准备时间：{row['prep_time']}")

            # 设置餐数乘数
            portions = st.number_input(
                f"这道菜准备吃几顿？(份数)",
                min_value=1,
                max_value=14,
                value=4 if idx == 0 else 1,  # 默认第一道做 4 顿午餐 Meal Prep
                key=f"portion_{idx}",
            )
            recipe_portions[title] = portions

            with st.expander("查看单份食材与烹饪步骤"):
                st.write("**食材列表：**")
                st.write(row["ingredients"])
                st.write("**制作步骤：**")
                st.write(row["instructions"])

# ==================== 5. 智能计算与合并采购清单 ====================
st.divider()
st.header("🛒 第二步：智能合并采购清单")


def parse_and_merge_ingredients(selected_rows, portions_map, pantry_list):
    """解析食材，乘以对应餐数，合并同类项，并扣除冰箱库存"""
    raw_ingredients = []

    for _, row in selected_rows.iterrows():
        title = row["title"]
        multiplier = portions_map.get(title, 1)

        ing_text = str(row["ingredients"])
        items = re.split(r"[|\n]", ing_text)

        for item in items:
            cleaned = item.strip().strip("•").strip()
            if cleaned:
                # 记录食材项与对应的餐数倍数
                raw_ingredients.append((cleaned, multiplier))

    # 去重与扣除冰箱库存
    shopping_items = []
    for item, mult in raw_ingredients:
        # 判断是否在冰箱已有库存中
        is_in_pantry = any(p.lower() in item.lower() for p in pantry_list if p)
        if not is_in_pantry:
            shopping_items.append((item, mult))

    # 合并相同食材，汇总餐数/剂量
    item_totals = {}
    for item, mult in shopping_items:
        item_totals[item] = item_totals.get(item, 0) + mult

    final_list = []
    for item, total_mult in item_totals.items():
        display_text = (
            f"{item} (需准备 {total_mult} 份量)" if total_mult > 1 else item
        )
        final_list.append({"完成": False, "食材项": display_text})

    return final_list


if selected_titles:
    selected_rows = df_recipes[df_recipes["title"].isin(selected_titles)]
    shopping_data = parse_and_merge_ingredients(
        selected_rows, recipe_portions, all_pantry
    )

    if shopping_data:
        st.write(
            "已根据你设置的**餐数倍数**进行自动汇总，并**扣除**了冰箱已有食材："
        )

        df_shopping = pd.DataFrame(shopping_data)

        # 无刷新可勾选表格
        edited_df = st.data_editor(
            df_shopping,
            column_config={
                "完成": st.column_config.CheckboxColumn(
                    "已买/已有",
                    help="点击勾选，标注已购买",
                    default=False,
                ),
                "食材项": st.column_config.TextColumn(
                    "采购项目 (已计算总份量)", disabled=True
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
        st.success("🎉 所选菜谱需要的食材你冰箱里全部都有，无需采购！")
else:
    st.warning("👈 请先在上方勾选至少一道菜谱。")