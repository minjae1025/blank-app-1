import streamlit as st
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import datetime
import matplotlib
from matplotlib import font_manager as fm, rcParams
from pathlib import Path
from matplotlib.colors import TwoSlopeNorm

# --- 폰트 설정 (이전과 동일) ---
def force_pretendard_font():
    font_path = Path(__file__).parent / "fonts" / "Pretendard-Bold.ttf"
    if font_path.exists():
        fm.fontManager.addfont(str(font_path))
        font_name = fm.FontProperties(fname=str(font_path)).get_name()
        rcParams["font.family"] = font_name
        rcParams["axes.unicode_minus"] = False
        return True
    else:
        rcParams["axes.unicode_minus"] = False
        return False
HAS_KR_FONT = force_pretendard_font()

# --- Streamlit 기본 설정 (이전과 동일) ---
st.set_page_config(layout="wide", page_title="NCEP/NCAR 해상 기온 시각화")
st.title("NOAA 일일 해상 2m 기온 자동 시각화")
st.markdown("데이터 소스: [NOAA PSL NCEP/NCAR Reanalysis 1](https://psl.noaa.gov/data/gridded/data.ncep.reanalysis.dailyavgs.html)")

# --- 데이터 소스 URL (이전과 동일) ---
BASE_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis.dailyavgs/surface_gauss/air.2m.gauss.{year}.nc"

# --- 데이터 로딩 함수 (단위 변환 추가됨) ---
@st.cache_data(show_spinner=False)
def load_and_slice_data(selected_date: datetime.date):
    year = selected_date.year
    data_url = BASE_URL.format(year=year)
    date_str = selected_date.strftime("%Y-%m-%d")
    try:
        try:
            ds = xr.open_dataset(data_url)
        except Exception:
            ds = xr.open_dataset(data_url, engine="pydap")
        da = (
            ds["air"]
            .sel(time=date_str, method='nearest')
            .sel(lat=slice(42, 28), lon=slice(120, 135))
            .squeeze()
        )
        da.load()
        
        # [수정] 켈빈(K) 단위를 섭씨(°C)로 변환
        da = da - 273.15
        da.attrs['units'] = 'degC'

        if hasattr(da, "values") and np.all(np.isnan(da.values)):
            return None
        return da
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        st.info("연도별 파일만 제공됩니다. 네트워크(방화벽/SSL) 또는 엔진(pydap, netCDF4) 설치 문제일 수 있어요.")
        return None

# --- 지도 시각화 함수 (이전과 동일) ---
def create_map_figure(data_array, selected_date):
    if data_array is None or getattr(data_array, "size", 0) == 0:
        return None
    fig, ax = plt.subplots(
        figsize=(10, 8),
        subplot_kw={"projection": ccrs.PlateCarree()}
    )
    norm = TwoSlopeNorm(vmin=-5, vcenter=10, vmax=30)
    cmap = "coolwarm"
    im = data_array.plot.pcolormesh(
        ax=ax, x="lon", y="lat", transform=ccrs.PlateCarree(),
        cmap=cmap, norm=norm, add_colorbar=False
    )
    ax.coastlines()
    ax.add_feature(cfeature.LAND, zorder=1, facecolor="lightgray", edgecolor="black")
    ax.add_feature(cfeature.BORDERS, linestyle=':')
    try:
        gl = ax.gridlines(draw_labels=True, linewidth=1, color="gray", alpha=0.5, linestyle="--")
        gl.top_labels = False
        gl.right_labels = False
    except Exception:
        ax.gridlines(linewidth=1, color="gray", alpha=0.5, linestyle="--")
    cbar = fig.colorbar(im, ax=ax, orientation="vertical", pad=0.05, aspect=40)
    cbar.set_label("해상 2m 기온 (°C)")
    ax.set_title(f"해상 2m 기온: {selected_date.strftime('%Y년 %m월 %d일')}", fontsize=16)
    fig.tight_layout()
    return fig

# --- UI 및 메인 로직 (이전과 동일) ---
st.sidebar.header("날짜 선택")
default_date = datetime.date.today() - datetime.timedelta(days=2)
selected_date = st.sidebar.date_input(
    "보고 싶은 날짜를 선택하세요",
    value=default_date,
    min_value=datetime.date(1948, 1, 1),
    max_value=default_date,
)
if selected_date:
    with st.spinner(f"{selected_date:%Y-%m-%d} 데이터를 불러오는 중..."):
        air_temp_data = load_and_slice_data(selected_date)
    if air_temp_data is not None and air_temp_data.size > 0:
        st.subheader(f"{selected_date:%Y년 %m월 %d일} 해상 2m 기온 지도")
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
        st.stop()