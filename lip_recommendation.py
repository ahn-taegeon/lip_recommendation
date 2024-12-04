import streamlit as st
import mysql.connector
import plotly.graph_objects as go
import pandas as pd
import colorsys
import math

# MySQL 데이터베이스 연결 설정
def create_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )


# 페이지 설정
st.set_page_config(page_title="Lip Recommendation System", page_icon="💄", layout="wide")

# 사이드바
st.sidebar.header("🌈 Select Your Preferences")

# 1. 퍼스널 컬러 선택 (중복 불가)
personal_color = st.sidebar.radio(
    "Choose your personal color:",
    ["Spring Warm", "Summer Cool", "Autumn Warm", "Winter Cool"]
)

# 2. 원하는 제형 선택 (중복 불가)
product_type = st.sidebar.selectbox(
    "Choose your desired formulation:",
    ["All", "Lipstick", "Lip Tint", "Lip Balm", "Lip Gloss", "Lip Liner"]
)

# 데이터베이스에서 선택한 퍼스널 컬러와 제형에 맞는 데이터 가져오기
conn = create_connection()
cursor = conn.cursor(dictionary=True)

if product_type == "All":
    query = """
        SELECT * FROM merge_data
        WHERE personal_color = %s
    """
    cursor.execute(query, (personal_color,))
else:
    product_type_mapping = {
        "Lipstick": "립스틱",
        "Lip Tint": "립틴트",
        "Lip Balm": "립밤",
        "Lip Gloss": "립글로스",
        "Lip Liner": "립라이너"
    }
    query = """
        SELECT * FROM merge_data
        WHERE personal_color = %s AND product_type = %s
    """
    cursor.execute(query, (personal_color, product_type_mapping[product_type]))

products = cursor.fetchall()

# 데이터가 있는지 확인하고 없을 경우 경고 메시지 표시
if not products:
    st.warning("No products found for the selected personal color and formulation. Please check the data or try a different selection.")
else:
    # 데이터프레임 생성
    df = pd.DataFrame(products)
    
    # 데이터프레임의 각 열을 float로 변환
    df['recommend_num'] = df['recommend_num'].astype(float)
    df['mean_h'] = df['mean_h'].astype(float) / 360.0  # 0~360 범위를 0~1로 변환
    df['mean_s'] = df['mean_s'].astype(float) / 100.0  # 0~100 범위를 0~1로 변환
    df['mean_v'] = df['mean_v'].astype(float) / 100.0  # 0~100 범위를 0~1로 변환
    df['rate'] = df['rate'].astype(float)
    df['pigmentation'] = df['pigmentation'].astype(float)
    df['longevity'] = df['longevity'].astype(float)
    df['smoothness'] = df['smoothness'].astype(float)

    # 추천 수 정규화
    df['recommend_num_normalized'] = (df['recommend_num'] - df['recommend_num'].min()) / (df['recommend_num'].max() - df['recommend_num'].min())

    # 슬라이더로 사용자에게 선택할 수 있도록 제공 (데이터의 최대, 최소값으로 자동 조정)
    selected_h = st.sidebar.slider("Select Hue (H):", min_value=float(df['mean_h'].min()) * 360, max_value=float(df['mean_h'].max()) * 360, value=float((df['mean_h'].min() + df['mean_h'].max()) / 2) * 360)
    selected_s = st.sidebar.slider("Select Saturation (S):", min_value=float(df['mean_s'].min()) * 100, max_value=float(df['mean_s'].max()) * 100, value=float((df['mean_s'].min() + df['mean_s'].max()) / 2) * 100)
    selected_v = st.sidebar.slider("Select Value (V):", min_value=float(df['mean_v'].min()) * 100, max_value=float(df['mean_v'].max()) * 100, value=float((df['mean_v'].min() + df['mean_v'].max()) / 2) * 100)

    # 선택한 색상과 각 제품 색상의 거리 계산
    def calculate_distance(h1, s1, h2, s2):
        dh = min(abs(h1 - h2), 1 - abs(h1 - h2)) * 2  # hue의 원형 거리 계산 (0~1 사이의 거리 계산)
        ds = abs(s1 - s2)
        return math.sqrt(dh**2 + ds**2)

    df['distance'] = df.apply(lambda row: calculate_distance(selected_h / 360.0, selected_s / 100.0, row['mean_h'], row['mean_s']), axis=1)

    # HSV 값을 RGB로 변환하여 각 점의 색상 설정
    def hsv_to_rgb(h, s, v):
        rgb = colorsys.hsv_to_rgb(h, s, v)
        return f'rgb({int(rgb[0] * 255)}, {int(rgb[1] * 255)}, {int(rgb[2] * 255)})'
    
    df['color_rgb'] = df.apply(lambda row: hsv_to_rgb(row['mean_h'], row['mean_s'], row['mean_v']), axis=1)

    # 평가지표 계산 (거리의 비중을 높임)
    df['score'] = df.apply(lambda row: (1 - row['distance']) * 0.7 + row['recommend_num_normalized'] * 0.15 + row['rate'] * 0.03 + row['pigmentation'] * 0.03 + row['longevity'] * 0.03 + row['smoothness'] * 0.03, axis=1)

    # 상위 3개의 점수를 가진 제품 추천
    top_3_products = df.nlargest(3, 'score')
    st.subheader("Top 3 Recommended Products")
    for idx, product in top_3_products.iterrows():
        st.write(f"**{product['name']}** - Product Color: {product['color']} - Score: {product['score']:.2f}")
        st.write(f"Price: {product['price']}, Rate: {product['rate']}, Pigmentation: {product['pigmentation']}, Longevity: {product['longevity']}, Smoothness: {product['smoothness']}")
        st.write("---")

    # go.Scatter를 사용하여 산포도 그래프 생성
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['mean_h'],
        y=df['mean_s'],
        mode='markers',
        marker=dict(
            size=12,
            color=df['color_rgb'],  # 각 점의 색상을 HSV 값에 기반해 설정
            line=dict(width=1, color='white'),
            opacity=0.9
        ),
        text=df.apply(lambda row: f"Name: {row['name']}<br>Color: {row['color']}", axis=1)  # 커서를 올렸을 때 제품명과 색상 표시
    ))

    # 선택한 색상 표시
    fig.add_trace(go.Scatter(
        x=[selected_h / 360.0],
        y=[selected_s / 100.0],
        mode='markers',
        marker=dict(
            size=15,
            color='red',  # 사용자가 선택한 색상을 빨간색으로 표시
            symbol='x'
        ),
        name='Selected Color'
    ))

    # x축과 y축의 범위를 데이터의 최대, 최소값으로 설정
    x_min, x_max = df['mean_h'].min(), df['mean_h'].max()
    y_min, y_max = df['mean_s'].min(), df['mean_s'].max()

    # 레이아웃 업데이트
    fig.update_layout(
        title='Product Distribution by Personal Color',
        title_font_size=20,
        xaxis_title='Hue',
        yaxis_title='Saturation',
        xaxis_title_font_size=16,
        yaxis_title_font_size=16,
        width=900,  # 그래프 너비 설정
        height=900,  # 그래프 높이 설정
        template='plotly_white',
        xaxis=dict(
            range=[x_min, x_max],  # 데이터의 최소, 최대값으로 범위 설정
            showgrid=True, gridcolor='lightgray', gridwidth=0.5,
            zeroline=False
        ),
        yaxis=dict(
            range=[y_min, y_max],  # 데이터의 최소, 최대값으로 범위 설정
            showgrid=False,
            zeroline=False
        ),
        plot_bgcolor='rgba(255, 250, 240, 0.5)',  # 전체 배경을 밝은 색상으로 변경
        dragmode='select'  # 커서를 더 잘 보이도록 드래그 모드를 줌으로 설정
    )

    # 그래프 표시
    st.plotly_chart(fig)

# 데이터베이스 연결 종료
cursor.close()
conn.close()

# 추가 정보 표시
st.info(
    "The graph shows the distribution of lip products based on your selected personal color. "
    "More product data can be added to expand the recommendations."
)
