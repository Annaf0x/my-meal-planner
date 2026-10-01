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

    # 给每道菜赋予唯一 ID
    if "recipe_id" not in df.columns:
        df["recipe_id"] = [f"recipe_{i}" for i in range(len(df))]

    return df


df_recipes = load_data()

# ==================== 3. Session State 状态初始化 ====================
if "random_indices" not in st.session_state:
    st.session_state.random_indices = random.sample(
        range(len(df_recipes)), min(3, len(df_recipes))
    )

if "selected_meals" not in st.session_state:
    st.session_state.selected_meals = {}

# 常见常备调料/冰箱库存默认清单
DEFAULT_PANTRY = ["盐", "黑胡椒", "食用油", "橄榄油", "生抽", "大蒜", "姜", "料酒", "水"]

if "my_fridge_items" not in st.session_state:
    st.session_state.my_fridge_items = ["盐", "黑胡椒", "食用油", "水"]


# ==================== 4. 数值解析与用量计算 ====================
def parse_and_multiply_ingredient(item_str, servings):
    """解析数字用量，直接乘以 servings 计算总数"""
    item_str = item_str.strip().strip("*")
    match = re.match(r"^([\d\.]+)\s*(.*)", item_str)

    if match:
        num = float(match.group(1))
        unit_and_name = match.group(2)
        total_num = num * servings

        if total_num.is_integer():
            formatted_num = str(int(total_num))
        else:
            formatted_num = f"{total_num:.2f}".rstrip("0").rstrip(".")

        return formatted_num, unit_and_name
    else:
        return None, f"{item_str} ({servings} 份)"


def generate_unified_shopping_list(selected_meals, fridge_items):
    """汇总并合并所有食材，同时剔除冰箱里已有的项目"""
    combined_ingredients = {}

    for recipe_id, info in selected_meals.items():
        servings = info["servings"]
        ing_text = str(info["row"]["ingredients"])
        items = re.split(r"[|\n]", ing_text)

        for item in items:
            cleaned = item.strip().strip("•").strip()
            if not cleaned:
                continue

            num, name_part = parse_and_multiply_ingredient(cleaned, servings)

            if num is not None:
                if name_part not in combined_ingredients:
                    combined_ingredients[name_part] = 0.0
                combined_ingredients[name_part] += float(num)
            else:
                combined_ingredients[name_part] = None

    shopping_rows = []
    for name_part, total_qty in combined_ingredients.items():
        # 检查是否在冰箱已有清单中
        is_in_fridge = any(
            f_item.lower() in name_part.lower() for f_item in fridge_items
        )

        if total_qty is not None:
            if total_qty.is_integer():
                display_qty = str(int(total_qty))
            else:
                display_qty = f"{total_qty:.2f}".rstrip("0").rstrip(".")
            display_text = f"{display_qty} {name_part}"
        else:
            display_text = name_part

        if not is_in_fridge:
            shopping_rows.append(
                {"完成状态": False, "采购项目 (已汇总总份量)": display_text}
            )

    return shopping_rows


# ==================== 5. 顶部 Header ====================
st.title("🥗 智能菜谱选餐与采购助手")
st.caption(
    "Pick meals → Set servings → Filter fridge inventory → Get shopping list"
)

# ==================== 6. 冰箱已有/常备调料管理 (我的冰箱里有什么) ====================
with st.expander("🧊 我的冰箱里有什么？(勾选已有常备食材/调料，采购清单将自动剔除)"):
    st.write("勾选你家中**已有**的调料或食材，生成的采购清单将不会包含它们：")

    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        st.session_state.my_fridge_items = st.multiselect(
            "冰箱/调味罐常备清单：",
            options=DEFAULT_PANTRY
            + [
                item
                for item in st.session_state.my_fridge_items
                if item not in DEFAULT_PANTRY
            ],
            default=st.session_state.my_fridge_items,
        )
    with col_f2:
        new_item = st.text_input("手动添加已有食材：", placeholder="如: 鸡蛋")
        if st.button("添加到冰箱"):
            if new_item and new_item not in st.session_state.my_fridge_items:
                st.session_state.my_fridge_items.append(new_item)
                st.rerun()

# ==================== 7. 第一步：Meal Picker ====================
st.header("1. 🎲 选餐 (Meal Picker)")

col_title, col_shuffle = st.columns([4, 1])
with col_shuffle:
    if st.button("🎲 换一批 / Shuffle", use_container_width=True):
        st.session_state.random_indices = random.sample(
            range(len(df_recipes)), min(3, len(df_recipes))
        )
        st.rerun()

card_cols = st.columns(3)
random_rows = df_recipes.iloc[st.session_state.random_indices]

for idx, (_, row) in enumerate(random_rows.iterrows()):
    r_id = row["recipe_id"]
    r_title = row["title"]

    with card_cols[idx]:
        with st.container(border=True):
            img_src = str(row["img_link"]).strip()
            if img_src.startswith("http"):
                st.image(img_src, use_container_width=True)
            else:
                st.info("🖼 暂无图片")

            st.subheader(r_title)
            st.caption(f"⏱ 准备时间：{row['prep_time']}")

            is_selected = r_id in st.session_state.selected_meals
            checked = st.checkbox(
                "Select / 选择这道菜", value=is_selected, key=f"chk_{r_id}"
            )

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

# 更多菜谱折叠浏览
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

# ==================== 8. 第二步：已选菜单汇总 ====================
st.divider()
st.header("2. 📋 已选菜单 (Selected Meals Summary)")

if st.session_state.selected_meals:
    summary_items = []
    for r_id, info in st.session_state.selected_meals.items():
        summary_items.append(
            f"• **{info['title']}**  —  `{info['servings']} servings`"
        )
    st.markdown("\n".join(summary_items))
else:
    st.info("💡 暂未选择任何菜谱。请在上方勾选感兴趣的菜谱。")

# ==================== 9. 第三步：统一采购清单 ====================
st.divider()
st.header("3. 🛒 采购清单 (Shopping List)")

shopping_data = []
if st.session_state.selected_meals:
    shopping_data = generate_unified_shopping_list(
        st.session_state.selected_meals, st.session_state.my_fridge_items
    )

    if shopping_data:
        df_shopping = pd.DataFrame(shopping_data)
        edited_df = st.data_editor(
            df_shopping,
            column_config={
                "完成状态": st.column_config.CheckboxColumn(
                    "已买", default=False
                ),
                "采购项目 (已汇总总份量)": st.column_config.TextColumn(
                    "采购项目与用量", disabled=True
                ),
            },
            disabled=["采购项目 (已汇总总份量)"],
            hide_index=True,
            use_container_width=True,
            key="unified_shopping_editor",
        )
    else:
        st.success(
            "🎉 选中的食材你的冰箱里都有啦！无需购买额外食材。"
        )

    # ==================== 10. 中式厨房替代品指南 ====================
    with st.expander("💡 常见西餐/外式调料 — 中式厨房替代指南 (Chinese Substitutes)"):
        st.markdown(
            """
        * **卡宴辣椒粉 (Cayenne Pepper)** $\rightarrow$ 普通中式细辣椒面 / 辣椒粉
        * **帕玛森芝士 / 芝士碎** $\rightarrow$ 可省去，或用少许盐和鲜味酱油提鲜
        * **酸奶油 (Sour Cream) / 蛋黄酱 (Mayonnaise)** $\rightarrow$ 浓稠无糖酸奶 / 轻食沙拉酱
        * **黄油 (Butter)** $\rightarrow$ 普通食用油 / 橄榄油（1:1 替代）
        * **欧芹 / 西洋菜 (Parsley)** $\rightarrow$ 香菜 / 芹菜叶
        * **第戎芥末酱 (Dijon Mustard)** $\rightarrow$ 黄芥末酱 / 少许青芥辣(Wasabi)+醋
        * **黑椒汁 / 鸡汤浓缩粉** $\rightarrow$ 浓汤宝 / 蚝油 + 现磨黑胡椒
        """
        )

    # ==================== 11. 保存与导出功能 ====================
    st.divider()
    st.header("💾 保存 / 导出菜单与清单")

    # 生成导出的文本内容
    export_text = "==== 🥗 本周菜谱计划 (Meal Plan) ====\n\n"
    for r_id, info in st.session_state.selected_meals.items():
        export_text += f"• {info['title']} ({info['servings']} 份/servings)\n"

    export_text += "\n==== 🛒 统一采购清单 (Shopping List) ====\n\n"
    if shopping_data:
        for item in shopping_data:
            export_text += f"[ ] {item['采购项目 (已汇总总份量)']}\n"
    else:
        export_text += "（无需采购，冰箱已有食材已满足所有菜谱需求）\n"

    st.download_button(
        label="📥 点击下载 txt 文本文件保存到本地",
        data=export_text,
        file_name="my_meal_plan_and_shopping_list.txt",
        mime="text/plain",
        type="primary",
        use_container_width=True,
    )

    with st.expander("📄 或直接复制以下文本导出到手机/Notion"):
        st.code(export_text, language="markdown")

else:
    st.warning("👈 请先选择至少一道菜谱以生成采购清单。")