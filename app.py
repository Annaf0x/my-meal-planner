import csv
import random
import re
import pandas as pd
import streamlit as st

# 指定你刚才生成的最干净的文件名
CSV_FILE = "recipes_for_notion_cn_cleaned.csv"

# 页面基本配置
st.set_page_config(
    page_title="单人高蛋白减重膳食规划助手", page_icon="🥗", layout="wide"
)

# 完整中西食材 Tag 库
INGREDIENT_TAGS = {
    "🥩 蛋白质 (含中式/速食)": [
        "鸡腿肉",
        "鸡胸肉",
        "牛肉馅",
        "牛肉粒",
        "三文鱼",
        "鳕鱼",
        "虾",
        "猪肉",
        "鸡蛋",
        "豆腐",
        "火锅牛肉片",
        "午餐肉",
        "冷冻水饺",
    ],
    "🥦 蔬菜/干货": [
        "西兰花",
        "菠菜",
        "荷兰豆",
        "蘑菇",
        "番茄",
        "洋葱",
        "黄瓜",
        "胡萝卜",
        "土豆",
        "白菜",
        "木耳",
        "腐竹",
        "金针菇",
    ],
    "🥫 中西调料/主食": [
        "米饭",
        "面条",
        "魔芋丝",
        "老干妈",
        "蚝油",
        "豆瓣酱",
        "酱油",
        "蒜",
        "姜",
        "葱",
        "黄油",
    ],
}

# Costco 与 大统华 归类关键词
COSTCO_KEYWORDS = [
    "鸡",
    "牛",
    "猪",
    "鱼",
    "虾",
    "蛋",
    "三文鱼",
    "鳕鱼",
    "土豆",
    "黄油",
    "奶酪",
    "米",
]
TNT_KEYWORDS = [
    "葱",
    "姜",
    "蒜",
    "酱油",
    "菠菜",
    "白菜",
    "荷兰豆",
    "蘑菇",
    "豆腐",
    "魔芋",
    "面",
    "番茄",
    "黄瓜",
    "木耳",
    "腐竹",
    "金针菇",
    "老干妈",
    "蚝油",
    "豆瓣酱",
    "水饺",
]


@st.cache_data
def load_data():
    try:
        # 优先读取清理后的干净文件，备用读取普通中文文件
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
        else:
            df = pd.read_csv("recipes_for_notion_cn.csv")
        return df
    except Exception:
        return None


import os

# ------------------- 界面 UI 搭建 -------------------
st.title("🥗 单人高蛋白减重膳食规划 & 自动采购助手")
st.caption(
    "基于 HelloFresh 菜谱库 | 支持中西清冰箱 Tag + Costco / 大统华采购单自动扣减"
)

df = load_data()

if df is None:
    st.warning(
        f"⚠️ 尚未找到 `{CSV_FILE}` 文件。请确保该文件保存在当前目录下并刷新页面！"
    )
    st.stop()

# 侧边栏：输入设置
st.sidebar.header("🗓️ 本周餐数需求")
lunch_num = st.sidebar.number_input(
    "🍱 本周午餐份数 (同款批量做)", min_value=0, max_value=7, value=5
)
dinner_num = st.sidebar.number_input(
    "🍳 本周晚餐份数 (快手不同样)", min_value=0, max_value=7, value=3
)

st.sidebar.markdown("---")
st.sidebar.header("🧊 冰箱现有食材 (清库存/中西杂货)")

pantry_selected = []
for category, tags in INGREDIENT_TAGS.items():
    st.sidebar.subheader(category)
    selected = st.sidebar.multiselect(f"选择现有 {category}", tags, key=category)
    pantry_selected.extend(selected)

# 自由文本补充输入
custom_pantry = st.sidebar.text_input(
    "✍️ 补充其他杂货/特有食材 (用逗号分隔)",
    placeholder="例：螺蛳粉, 咸鸭蛋, 火锅蘸料",
)
if custom_pantry:
    pantry_selected.extend([x.strip() for x in custom_pantry.split(",") if x.strip()])

# 生成按钮
if st.button("🎲 一键生成本周膳食计划与采购单", type="primary"):
    working_df = df.copy()

    # 优先匹配冰箱含有的食材
    def match_score(row):
        ing_str = str(row.get("ingredients", "")) + str(row.get("title", ""))
        score = sum(1 for tag in pantry_selected if tag in ing_str)
        return score

    working_df["score"] = working_df.apply(match_score, axis=1)
    working_df = working_df.sort_values(by="score", ascending=False)

    # 摇号午餐（选 1 道匹配度最高的菜）
    top_candidates = working_df.head(30)
    lunch_recipe = (
        top_candidates.sample(1).iloc[0]
        if len(top_candidates) > 0
        else df.sample(1).iloc[0]
    )

    # 摇号晚餐（选 N 道不重复的菜）
    remaining_df = working_df[working_df["title"] != lunch_recipe["title"]]
    dinner_recipes = (
        remaining_df.sample(min(dinner_num, len(remaining_df)))
        if dinner_num > 0
        else pd.DataFrame()
    )

    # 展示计划
    col1, col2 = st.columns(2)

    selected_all = []

    with col1:
        st.subheader(f"🍱 本周午餐 (Batch Cooking x {lunch_num} 份)")
        if lunch_num > 0:
            st.success(f"**{lunch_recipe['title']}**")
            st.write(f"⏱️ 准备/烹饪时间: {lunch_recipe.get('prep_time', '15-20 分钟')}")
            st.write(
                f"📝 **食材**: {lunch_recipe.get('ingredients', '暂无')}"
            )
            st.write(f"📖 **步骤**:\n{lunch_recipe.get('instructions', '暂无')}")

            # 中国胃替代提示
            asian_sauces = [
                s for s in ["老干妈", "蚝油", "豆瓣酱"] if s in pantry_selected
            ]
            if asian_sauces:
                st.info(
                    f"💡 **中国胃小贴士**: 酱汁部分可直接替换为你冰箱里的【{', '.join(asian_sauces)}】，味道更赞且更省事！"
                )

            lunch_dict = lunch_recipe.to_dict()
            lunch_dict["is_lunch"] = True
            selected_all.append(pd.Series(lunch_dict))

    with col2:
        st.subheader(f"🍳 本周晚餐 (快手不同样 x {dinner_num} 份)")
        if dinner_num > 0 and not dinner_recipes.empty:
            for idx, (_, d_row) in enumerate(dinner_recipes.iterrows(), 1):
                with st.expander(f"晚餐 {idx}: {d_row['title']}"):
                    st.write(
                        f"⏱️ 时间: {d_row.get('prep_time', '15-20 分钟')}"
                    )
                    st.write(f"📝 食材: {d_row.get('ingredients', '暂无')}")
                    st.write(f"📖 步骤:\n{d_row.get('instructions', '暂无')}")

                d_dict = d_row.to_dict()
                d_dict["is_lunch"] = False
                selected_all.append(pd.Series(d_dict))

    # 生成购物清单并自动扣减冰箱库存
    st.markdown("---")
    st.header("🛒 智能合并采购清单 (已自动扣除冰箱现有食材)")

    if selected_all:
        selected_df = pd.DataFrame(selected_all)

        costco_list = set()
        tnt_list = set()

        for idx, row in selected_df.iterrows():
            ings = str(row.get("ingredients", "")).split("|")
            multiplier = lunch_num if row.get("is_lunch", False) else 1

            for ing in ings:
                clean_ing = ing.strip()
                if not clean_ing:
                    continue

                item_display = (
                    f"{clean_ing} (x{multiplier} 份量)"
                    if multiplier > 1
                    else clean_ing
                )

                if any(k in clean_ing for k in COSTCO_KEYWORDS):
                    costco_list.add(item_display)
                else:
                    tnt_list.add(item_display)

        # 过滤冰箱已有食材
        def filter_pantry(item_list):
            final_list = []
            for item in item_list:
                if not any(tag in item for tag in pantry_selected if tag):
                    final_list.append(item)
            return final_list

        costco_final = filter_pantry(costco_list)
        tnt_final = filter_pantry(tnt_list)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📦 Costco 采购清单 (大包装/硬货)")
            if costco_final:
                for item in sorted(costco_final):
                    st.checkbox(f"{item}", key=f"costco_{item}")
            else:
                st.info("🎉 现有库存足够，无需在 Costco 补充大件！")

        with c2:
            st.subheader("🥬 大统华 (T&T) 采购清单 (新鲜蔬菜/调味料)")
            if tnt_final:
                for item in sorted(tnt_final):
                    st.checkbox(f"{item}", key=f"tnt_{item}")
            else:
                st.info("🎉 现有库存足够，无需购买额外散件！")