import streamlit as st
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import datetime

# --- Pretendard-Bold.ttf 폰트 강제 등록 (원본 코드와 동일) ---
import matplotlib
from matplotlib import font_manager as fm, rcParams
from pathlib import Path
from matplotlib.colors import TwoSlopeNorm

def force_pretendard_font():
    """
    앱 폴더 fonts/Pretendard-Bold.ttf 를 강제로 등록해 한글 표시를 보장
    """
    font_path = Path(__file__).parent / "fonts" / "Pretendard-Bold.ttf"
    if font_path.exists():
        fm.fontManager.addfont(str(font_path))
        font_name = fm.FontProperties(fname=str(font_path)).get_name()
        rcParams["font.family"] = font_name
        rcParams["axes.unicode_minus"] = False # 마이너스 기호 깨짐 방지
        return True
    else:
        rcParams["axes.unicode_minus"] = False
        return False

HAS_KR_FONT = force_pretendard_font()


# --- Streamlit 기본 설정 ---
st.set_page_config(layout="wide", page_title="NCEP/NCAR 지상 기온 시각화")
st.title("NOAA 일일 지상 2m 기온 자동 시각화")
st.markdown("데이터 소스: [NOAA PSL NCEP/NCAR Reanalysis 1](https://psl.noaa.gov/data/gridded/data.ncep.reanalysis.dailyavgs.html)")

# --- [변경] 연도별 데이터 소스 URL (OPeNDAP) ---
# 지상 2m 기온(air.2m.gauss) 데이터셋으로 변경
BASE_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis.dailyavgs/surface_gauss/air.2m.gauss.{year}.nc"

# --- 데이터 로딩 함수 ---
@st.cache_data(show_spinner=False)
def load_and_slice_data(selected_date: datetime.date):
    """
    선택한 날짜(YYYY-MM-DD)의 한국/동중국해 인근(위도 28~42N, 경도 120~135E) 지상 기온을 로드.
    """
    year = selected_date.year
    data_url = BASE_URL.format(year=year)
    date_str = selected_date.strftime("%Y-%m-%d")

    try:
        # 1차 시도: 기본 엔진
        try:
            ds = xr.open_dataset(data_url)
        except Exception:
            # 2차 시도: pydap 백업
            ds = xr.open_dataset(data_url, engine="pydap")

        # [변경] 변수 선택 ('sst' -> 'air') 및 공간/시간 슬라이스
        da = (
            ds["air"]
            .sel(time=date_str, method='nearest')  # 1. 먼저 시간 선택 (method='nearest' 적용)
            .sel(lat=slice(42, 28), lon=slice(120, 135)) # 2. 그 다음 공간(위도/경도) 범위 선택
            .squeeze()
        )

        # 실제 값 로드
        da.load()

        # 결측/마스킹 처리를 위한 방어 코드
        if hasattr(da, "values") and np.all(np.isnan(da.values)):
            return None

        return da

    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        st.info("연도별 파일만 제공됩니다. 네트워크(방화벽/SSL) 또는 엔진(pydap, netCDF4) 설치 문제일 수 있어요.")
        return None

# --- 지도 시각화 함수 ---
def create_map_figure(data_array, selected_date):
    if data_array is None or getattr(data_array, "size", 0) == 0:
        return None

    fig, ax = plt.subplots(
        figsize=(10, 8),
        subplot_kw={"projection": ccrs.PlateCarree()}
    )

    # [변경] 기온 데이터에 맞는 색상 정규화 설정
    # 10도를 중심으로, 영하(-5도)는 파란색, 영상(30도)은 붉은색으로 표현
    norm = TwoSlopeNorm(vmin=-5, vcenter=10, vmax=30)
    cmap = "coolwarm" # 더위/추위를 나타내기 좋은 'coolwarm' 컬러맵 사용

    im = data_array.plot.pcolormesh(
        ax=ax,
        x="lon",
        y="lat",
        transform=ccrs.PlateCarree(),
        cmap=cmap,
        norm=norm,
        add_colorbar=False
    )

    ax.coastlines()
    ax.add_feature(cfeature.LAND, zorder=1, facecolor="lightgray", edgecolor="black")
    ax.add_feature(cfeature.BORDERS, linestyle=':')

    # 그리드라인 및 레이블 설정
    try:
        gl = ax.gridlines(draw_labels=True, linewidth=1, color="gray", alpha=0.5, linestyle="--")
        gl.top_labels = False
        gl.right_labels = False
    except Exception:
        ax.gridlines(linewidth=1, color="gray", alpha=0.5, linestyle="--")

    # [변경] 컬러바 및 제목 라벨 변경
    cbar = fig.colorbar(im, ax=ax, orientation="vertical", pad=0.05, aspect=40)
    cbar.set_label("지상 2m 기온 (°C)")
    ax.set_title(f"지상 2m 기온: {selected_date.strftime('%Y년 %m월 %d일')}", fontsize=16)

    fig.tight_layout()
    return fig


# --- 사이드바 UI ---
st.sidebar.header("날짜 선택")
# 최신 데이터 지연을 고려해 2일 전을 기본값으로 설정
default_date = datetime.date.today() - datetime.timedelta(days=2)
selected_date = st.sidebar.date_input(
    "보고 싶은 날짜를 선택하세요",
    value=default_date,
    min_value=datetime.date(1948, 1, 1), # [변경] 데이터셋 시작 연도에 맞게 수정
    max_value=default_date,
)

# --- 메인 로직 ---
if selected_date:
    with st.spinner(f"{selected_date:%Y-%m-%d} 데이터를 불러오는 중..."):
        # [변경] 변수 이름 변경 sst_data -> air_temp_data
        air_temp_data = load_and_slice_data(selected_date)

    if air_temp_data is not None and air_temp_data.size > 0:
        # [변경] 제목 텍스트 변경
        st.subheader(f"{selected_date:%Y년 %m월 %d일} 지상 2m 기온 지도")
        fig = create_map_figure(air_temp_data, selected_date)
        if fig:
            st.pyplot(fig, clear_figure=True)

        with st.expander("데이터 미리보기"):
            st.write(air_temp_data)
            st.caption(
                f"lat: {float(air_temp_data.lat.min())}~{float(air_temp_data.lat.max())}, "
                f"lon: {float(air_temp_data.lon.min())}~{float(air_temp_data.lon.max())}"
            )
    elif air_temp_data is not None:
        st.warning("선택하신 날짜에 해당하는 데이터가 없습니다. 다른 날짜를 선택해 주세요.")
    else:
        # 데이터 로딩 실패 시 여기서 멈춤
        st.stop()