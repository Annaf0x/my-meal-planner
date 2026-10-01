import html
import random
import re
import pandas as pd
import streamlit as st

# ==================== 1. 页面基本配置 ====================
st.set_page_config(
    page_title="极简高蛋白减脂 Meal Planner & 采购助手",
    page_icon="🥗",
    layout="wide",
)


# ==================== 2. 数据加载与预处理 ====================
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

    # 兼容图片字段
    if "image_url" in df.columns:
        df["img_link"] = df["image_url"].fillna("")
    elif "image" in df.columns:
        df["img_link"] = df["image"].fillna("")
    else:
        df["img_link"] = ""

    # 给每道菜赋予唯一 ID，为后续 Meal Planner 及 Inventory 留出接口
    if "recipe_id" not in df.columns:
        df["recipe_id"] = [f"recipe_{i}" for i in range(len(df))]

    return df


df_recipes = load_data()

# ==================== 3. Session State 状态初始化 ====================
# 初始化 3 个随机推荐菜谱的索引
if "random_indices" not in st.session_state:
    st.session_state.random_indices = random.sample(
        range(len(df_recipes)), min(3, len(df_recipes))
    )

# 初始化已选菜谱及其 Servings (为 Weekly Planner & Inventory 留接口)
# 结构: { recipe_id: {"title": str, "servings": int, "row": pd.Series} }
if "selected_meals" not in st.session_state:
    st.session_state.selected_meals = {}

# ==================== 4. 辅助函数：食材分类与合并 ====================
PRODUCE_KEYWORDS = [
    "菜",
    "蔬",
    "果",
    "葱",
    "姜",
    "蒜",
    "椒",
    "菇",
    "土豆",
    "番茄",
    "西红柿",
    "洋葱",
    "胡萝卜",
    "黄瓜",
    "菠菜",
    "生菜",
    "柠檬",
    "produce",
    "onion",
    "tomato",
    "carrot",
    "garlic",
]
MEAT_KEYWORDS = [
    "肉",
    "鸡",
    "牛",
    "猪",
    "羊",
    "虾",
    "鱼",
    "蛋",
    "排骨",
    "培根",
    "三文鱼",
    "海鲜",
    "meat",
    "seafood",
    "beef",
    "chicken",
    "pork",
    "shrimp",
    "salmon",
    "fish",
]


def categorize_ingredient(item_name):
    """将食材自动归类为 Produce, Meat / Seafood, Pantry"""
    name_lower = item_name.lower()
    if any(kw in name_lower for kw in MEAT_KEYWORDS):
        return "🥩 Meat / Seafood (肉类海鲜)"
    elif any(kw in name_lower for kw in PRODUCE_KEYWORDS):
        return "🥬 Produce (农货蔬菜)"
    else:
        return "🧂 Pantry (调味干货/其他)"


def generate_categorized_shopping_list(selected_meals):
    """根据选中的菜谱及 Servings 自动计算并归类 Shopping List"""
    raw_ingredients = []

    for recipe_id, info in selected_meals.items():
        servings = info["servings"]
        ing_text = str(info["row"]["ingredients"])
        items = re.split(r"[|\n]", ing_text)

        for item in items:
            cleaned = item.strip().strip("•").strip()
            if cleaned:
                raw_ingredients.append((cleaned, servings))

    # 合并同类项（累加 Servings 份量）
    item_totals = {}
    for item, serv in raw_ingredients:
        item_totals[item] = item_totals.get(item, 0) + serv

    # 按类别分组
    categorized_data = {
        "🥬 Produce (农货蔬菜)": [],
        "🥩 Meat / Seafood (肉类海鲜)": [],
        "🧂 Pantry (调味干货/其他)": [],
    }

    for item, total_serv in item_totals.items():
        cat = categorize_ingredient(item)
        display_text = (
            f"{item} — {total_serv} 份量" if total_serv > 1 else item
        )
        categorized_data[cat].append({"已购/已有": False, "食材项目": display_text})

    return categorized_data


# ==================== 5. 顶部 Header ====================
st.title("🥗 智能菜谱选餐与采购助手")
st.caption("Pick meals → Set servings → Get categorized shopping list")

# ==================== 6. 第一步：Meal Picker (3 个随机推荐 + Shuffle) ====================
st.header("1. 🎲 选餐 (Meal Picker)")

col_title, col_shuffle = st.columns([4, 1])
with col_shuffle:
    if st.button("🎲 换一批 / Shuffle", use_container_width=True):
        st.session_state.random_indices = random.sample(
            range(len(df_recipes)), min(3, len(df_recipes))
        )
        st.rerun()

# 展示 3 个随机卡片
card_cols = st.columns(3)
random_rows = df_recipes.iloc[st.session_state.random_indices]

for idx, (_, row) in enumerate(random_rows.iterrows()):
    r_id = row["recipe_id"]
    r_title = row["title"]

    with card_cols[idx]:
        with st.container(border=True):
            # 渲染图片
            img_src = str(row["img_link"]).strip()
            if img_src.startswith("http"):
                st.image(img_src, use_container_width=True)
            else:
                st.info("🖼 暂无图片")

            st.subheader(r_title)
            st.caption(f"⏱ 准备时间：{row['prep_time']}")

            # 选择框状态维护
            is_selected = r_id in st.session_state.selected_meals
            checked = st.checkbox(
                "Select / 选择这道菜", value=is_selected, key=f"chk_{r_id}"
            )

            # Servings 份数调节
            current_servings = (
                st.session_state.selected_meals[r_id]["servings"]
                if is_selected
                else 2
            )
            servings = st.number_input(
                "Servings / 几人份",
                min_value=1,
                max_value=14,
                value=current_servings,
                key=f"serv_{r_id}",
            )

            # 动态更新全局 Session Selected Meals
            if checked:
                st.session_state.selected_meals[r_id] = {
                    "title": r_title,
                    "servings": servings,
                    "row": row,
                }
            else:
                if r_id in st.session_state.selected_meals:
                    del st.session_state.selected_meals[r_id]

            with st.expander("查看食材与步骤"):
                st.write("**食材：**", row["ingredients"])
                st.write("**步骤：**", row["instructions"])

# 更多菜谱折叠浏览 (Browse More)
with st.expander("🔍 浏览全部菜谱 / Browse All Recipes"):
    search_kw = st.text_input("搜索菜谱名称或食材：", "")
    browse_df = (
        df_recipes[
            df_recipes["title"].str.contains(search_kw, case=False, na=False)
            | df_recipes["ingredients"].str.contains(
                search_kw, case=False, na=False
            )
        ]
        if search_kw
        else df_recipes
    )

    for _, b_row in browse_df.head(10).iterrows():
        b_id = b_row["recipe_id"]
        b_selected = b_id in st.session_state.selected_meals
        b_cols = st.columns([3, 1, 1])
        with b_cols[0]:
            st.write(f"**{b_row['title']}** ({b_row['prep_time']})")
        with b_cols[1]:
            b_chk = st.checkbox(
                "选择",
                value=b_selected,
                key=f"b_chk_{b_id}",
                label_visibility="collapsed",
            )
        with b_cols[2]:
            b_serv = st.number_input(
                "份数",
                min_value=1,
                max_value=10,
                value=2,
                key=f"b_serv_{b_id}",
                label_visibility="collapsed",
            )

        if b_chk:
            st.session_state.selected_meals[b_id] = {
                "title": b_row["title"],
                "servings": b_serv,
                "row": b_row,
            }
        elif b_id in st.session_state.selected_meals and not b_chk:
            del st.session_state.selected_meals[b_id]

# ==================== 7. 第二步：已选菜单汇总 (Selected Meals) ====================
st.divider()
st.header("2. 📋 已选菜单 (Selected Meals Summary)")

if st.session_state.selected_meals:
    summary_items = []
    for r_id, info in st.session_state.selected_meals.items():
        summary_items.append(f"• **{info['title']}**  —  `{info['servings']} servings`")
    st.markdown("\n".join(summary_items))
else:
    st.info("💡 暂未选择任何菜谱。请在上方勾选感兴趣的菜谱。")

# ==================== 8. 第三步：分组采购清单 (Categorized Shopping List) ====================
st.divider()
st.header("3. 🛒 采购清单 (Shopping List)")

if st.session_state.selected_meals:
    categorized_list = generate_categorized_shopping_list(
        st.session_state.selected_meals
    )

    tab_produce, tab_meat, tab_pantry = st.tabs(
        [
            "🥬 Produce (农货蔬菜)",
            "🥩 Meat / Seafood (肉类海鲜)",
            "🧂 Pantry (调味干货)",
        ]
    )

    tabs_map = {
        "🥬 Produce (农货蔬菜)": tab_produce,
        "🥩 Meat / Seafood (肉类海鲜)": tab_meat,
        "🧂 Pantry (调味干货/其他)": tab_pantry,
    }

    for category, items in categorized_list.items():
        target_tab = tabs_map[category]
        with target_tab:
            if items:
                df_cat = pd.DataFrame(items)
                st.data_editor(
                    df_cat,
                    column_config={
                        "已购/已有": st.column_config.CheckboxColumn(
                            "状态", default=False
                        ),
                        "食材项目": st.column_config.TextColumn(
                            "项目名称 (含汇总份量)", disabled=True
                        ),
                    },
                    disabled=["食材项目"],
                    hide_index=True,
                    use_container_width=True,
                    key=f"editor_{category}",
                )
            else:
                st.caption("该分类下暂无所需食材。")
else:
    st.warning("👈 请先选择至少一道菜谱以生成采购清单。")