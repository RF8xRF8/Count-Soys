import cv2
import numpy as np
from skimage.filters import threshold_li, threshold_otsu, threshold_triangle, threshold_yen

from ..core.clock import beijing_now


def _threshold_candidates(gray: np.ndarray) -> list[np.ndarray]:
    methods = (threshold_otsu, threshold_li, threshold_yen, threshold_triangle)
    candidates = []
    for method in methods:
        try:
            threshold = method(gray)
            candidates.append(gray > threshold)
        except ValueError:
            continue
    return candidates


def _hsv_cluster_mask(img_bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    pixels = hsv.reshape((-1, 3)).astype(np.float32)
    pixels[:, 0] /= 179.0
    pixels[:, 1:] /= 255.0
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.2)
    cv2.setRNGSeed(42)
    _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    scores = []
    for center in centers:
        hue = center[0] * 179.0
        yellow_score = max(0.0, 1.0 - abs(hue - 22.0) / 30.0)
        scores.append(center[1] * 0.65 + center[2] * 0.2 + yellow_score * 0.15)
    selected = int(np.argmax(scores))
    return np.uint8(labels.reshape(hsv.shape[:2]) == selected) * 255


def _particle_masks(img_bgr: np.ndarray, mode: str, blurred: np.ndarray, params: dict) -> list[np.ndarray]:
    if mode == "beans":
        # ImageJ's color-threshold workflow is represented by Lab b*: beans
        # remain bright in this channel even when RGB brightness changes.
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        yellow = lab[:, :, 2]
        delta = int(params.get("yellow_delta", 25))
        baseline = float(np.median(yellow))
        candidates = [yellow > baseline + delta]
        candidates.append(_hsv_cluster_mask(img_bgr) > 0)
        candidates.extend(_threshold_candidates(yellow))
        # Keep intensity-based candidates so the detector can fall back when
        # bean color differs from the training examples.
        candidates.extend(_threshold_candidates(blurred))
        return [np.uint8(mask) * 255 for mask in candidates]

    threshold_mode = params.get("threshold_mode", "otsu_inv")
    flag = cv2.THRESH_BINARY_INV if threshold_mode == "otsu_inv" else cv2.THRESH_BINARY
    if threshold_mode in {"otsu_inv", "otsu"}:
        _, mask = cv2.threshold(blurred, 0, 255, flag + cv2.THRESH_OTSU)
        return [mask]
    return [np.uint8(mask) * 255 for mask in _threshold_candidates(blurred)]


def _segment_particles(img_bgr: np.ndarray, binary: np.ndarray, min_area: int, ratio: float, max_area: int | None = None) -> list[dict]:
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    component_count, component_labels, component_stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    cleaned = np.zeros_like(binary)
    for component_id in range(1, component_count):
        if component_stats[component_id, cv2.CC_STAT_AREA] >= max(20, min_area // 4):
            cleaned[component_labels == component_id] = 255
    binary = cleaned
    sure_bg = cv2.dilate(binary, kernel, iterations=2)
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    _, sure_fg = cv2.threshold(dist, max(0.01, ratio) * dist.max(), 255, 0)
    sure_fg = np.uint8(sure_fg)
    unknown = cv2.subtract(sure_bg, sure_fg)
    _, markers = cv2.connectedComponents(sure_fg)
    markers = markers + 1
    markers[unknown == 255] = 0
    cv2.watershed(img_bgr, markers)

    regions = []
    for label in range(2, int(markers.max()) + 1):
        mask = np.uint8(markers == label)
        area = int(cv2.countNonZero(mask))
        if area < min_area or (max_area is not None and area > max_area):
            continue
        regions.append((mask, area))

    instances = []
    for mask, area in regions:
        area = int(cv2.countNonZero(mask))
        if area < min_area or (max_area is not None and area > max_area):
            continue
        moments = cv2.moments(mask)
        if moments["m00"] == 0:
            continue
        contour_points = cv2.findNonZero(mask)
        (circle_x, circle_y), radius = cv2.minEnclosingCircle(contour_points)
        if circle_x - radius < 0 or circle_y - radius < 0 or circle_x + radius >= img_bgr.shape[1] or circle_y + radius >= img_bgr.shape[0]:
            continue
        instances.append({"id": len(instances) + 1, "x": round(moments["m10"] / moments["m00"]), "y": round(moments["m01"] / moments["m00"]), "area": area, "radius": max(5, round(radius))})
    return instances


def count_objects(img_bgr: np.ndarray, mode: str, params: dict) -> tuple[np.ndarray, list[dict], list[str]]:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    default_min_area = 500 if mode == "beans" else 100
    min_area = max(int(params.get("min_area", default_min_area)), 20)
    if mode == "beans":
        default_max_area = 8000 if min(img_bgr.shape[:2]) >= 1000 else 5000
        max_area = int(params.get("max_area", default_max_area))
    else:
        max_area = None
    default_ratio = 0.6 if mode == "beans" else 0.5
    ratio = float(params.get("fg_ratio", default_ratio))
    masks = _particle_masks(img_bgr, mode, blurred, params)
    candidates = [_segment_particles(img_bgr, mask, min_area, ratio, max_area) for mask in masks]
    selected_index = max(range(len(candidates)), key=lambda index: (len(candidates[index]), -abs(np.median([item["area"] for item in candidates[index]]) - 3000) if candidates[index] else -999999), default=0)
    instances = list(candidates[selected_index]) if candidates else []
    if mode == "beans" and selected_index == 0 and len(candidates) > 2:
        for item in candidates[2]:
            if not any((item["x"] - current["x"]) ** 2 + (item["y"] - current["y"]) ** 2 < 35 ** 2 for current in instances):
                instances.append(item)
    median_area = float(np.median([item["area"] for item in instances])) if instances else 1.0
    for index, item in enumerate(instances, start=1):
        item["id"] = index
        item["confidence"] = round(max(0.0, min(1.0, 1.0 - abs(item["area"] - median_area) / median_area)), 2)
    annotated = img_bgr.copy()

    draw_number = params.get("draw_number", True)
    # 豆子的描边比药片略粗一点，在手机上看标注圈更清楚。
    outline_width = 2 if mode == "beans" else 1
    for item in instances:
        point = (item["x"], item["y"])
        circle_color = (0, 215, 255) if item["confidence"] < 0.65 else (0, 0, 255)
        cv2.circle(annotated, point, item["radius"], circle_color, outline_width, cv2.LINE_AA)
        if draw_number:
            text = str(item["id"])
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.68 if len(text) < 3 else 0.55
            (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, 1)
            label_position = (point[0] - text_width // 2, point[1] + (text_height - baseline) // 2)
            cv2.putText(annotated, text, label_position, font, scale, (0, 0, 255), 1, cv2.LINE_AA)

    timestamp = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(annotated, f"Count: {len(instances)}", (24, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.65, (0, 0, 255), 2, cv2.LINE_AA)
    timestamp_y = annotated.shape[0] - 24
    cv2.putText(annotated, timestamp, (24, timestamp_y), cv2.FONT_HERSHEY_SIMPLEX, 0.95, (0, 0, 255), 2, cv2.LINE_AA)
    return annotated, instances, []
