"""
core/figure.py - 사업지구 안쪽만 남긴(바깥은 투명) 도면 PNG + 월드파일. QGIS 에 끌어 넣으면 제 위치에 놓인다.
"""
import cv2
import numpy as np

WKT = {
    5186: 'PROJCS["Korea_2000_Central_Belt_2010",GEOGCS["GCS_Korea_2000",DATUM["D_Korea_2000",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
          'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",200000.0],'
          'PARAMETER["False_Northing",600000.0],PARAMETER["Central_Meridian",127.0],PARAMETER["Scale_Factor",1.0],'
          'PARAMETER["Latitude_Of_Origin",38.0],UNIT["Meter",1.0]]',
    3857: 'PROJCS["WGS_1984_Web_Mercator_Auxiliary_Sphere",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
          'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Mercator_Auxiliary_Sphere"],PARAMETER["False_Easting",0.0],'
          'PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",0.0],PARAMETER["Standard_Parallel_1",0.0],'
          'PARAMETER["Auxiliary_Sphere_Type",0.0],UNIT["Meter",1.0]]',
}


def write_site_png(img_rgb, contour, A, crs, path, margin=6):
    """img_rgb: 쪽 그림, contour: 사업지구 경계(쪽 px), A: 쪽 px -> crs 2x3, path: .png (같은 이름 .pgw/.prj 도 쓴다).
    반환: 지상 크기(가로m, 세로m) 또는 None"""
    H, W = img_rgb.shape[:2]
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.int32(np.round(contour))], 255)
    k = 2 * margin + 1
    m = cv2.GaussianBlur(cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))), (0, 0), 1.2)   # 경계선이 잘리지 않게
    ys, xs = np.nonzero(m > 0)
    if not len(xs):
        return None
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    rgba = np.dstack([img_rgb[:, :, ::-1], m])[y0:y1, x0:x1]
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), rgba)
    a00, a01, a02 = A[0]
    a10, a11, a12 = A[1]
    C = a00 * (x0 + .5) + a01 * (y0 + .5) + a02          # 월드파일은 왼쪽 위 픽셀 '중심' 좌표
    F = a10 * (x0 + .5) + a11 * (y0 + .5) + a12
    path.with_suffix(".pgw").write_text("\n".join(repr(float(v)) for v in (a00, a10, a01, a11, C, F)))
    path.with_suffix(".prj").write_text(WKT[crs])
    return float(np.hypot(a00, a10) * (x1 - x0)), float(np.hypot(a01, a11) * (y1 - y0))
