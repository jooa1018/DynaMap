from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List


def _arrow(fig, x0, y0, x1, y1, text="", color=None):
    fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=3, arrowsize=1.2, text=text)


def circular_motion_figure(speed: float, radius: float, tangential_accel: float = 0.0) -> Any:
    import plotly.graph_objects as go
    radius = max(radius, 0.1)
    speed = max(speed, 0.0)
    an = speed ** 2 / radius if radius else 0
    theta = [i * 2 * math.pi / 240 for i in range(241)]
    x = [radius * math.cos(t) for t in theta]
    y = [radius * math.sin(t) for t in theta]
    point_angle = math.pi / 4
    px, py = radius * math.cos(point_angle), radius * math.sin(point_angle)
    tangent = (-math.sin(point_angle), math.cos(point_angle))
    normal = (-math.cos(point_angle), -math.sin(point_angle))
    scale_v = radius * 0.09 * (1 + min(speed, 30) / 12)
    scale_a = radius * 0.06 * (1 + min(an, 30) / 12)
    scale_at = radius * 0.06 * (1 + min(abs(tangential_accel), 30) / 12)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="경로"))
    fig.add_trace(go.Scatter(x=[0], y=[0], mode="markers+text", text=["중심"], textposition="bottom center", name="중심"))
    fig.add_trace(go.Scatter(x=[px], y=[py], mode="markers+text", text=["물체"], textposition="top center", name="물체"))
    _arrow(fig, px, py, px + tangent[0] * scale_v, py + tangent[1] * scale_v, "v")
    _arrow(fig, px, py, px + normal[0] * scale_a, py + normal[1] * scale_a, "aₙ")
    if abs(tangential_accel) > 1e-9:
        direction = 1 if tangential_accel >= 0 else -1
        _arrow(fig, px, py, px + tangent[0] * scale_at * direction, py + tangent[1] * scale_at * direction, "aₜ")
    fig.update_layout(title=f"원운동: aₙ = v²/r = {an:.2f} m/s²", xaxis=dict(scaleanchor="y", scaleratio=1, zeroline=True), yaxis=dict(zeroline=True), height=430, margin=dict(l=10, r=10, t=50, b=10), showlegend=False)
    return fig


def energy_bar_figure(T1: float, V1: float, Unc: float, T2: float, V2: float) -> Any:
    import plotly.graph_objects as go
    labels = ["처음 운동 T1", "처음 위치 V1", "비보존 일 U_nc", "나중 운동 T2", "나중 위치 V2"]
    vals = [T1, V1, Unc, T2, V2]
    fig = go.Figure(data=[go.Bar(x=labels, y=vals)])
    fig.update_layout(title="에너지 항 비교", height=360, margin=dict(l=10, r=10, t=50, b=80))
    return fig


def incline_fbd_figure(theta_deg: float = 30, friction: bool = True, motion_down: bool = True) -> Any:
    import plotly.graph_objects as go
    theta = math.radians(theta_deg)
    fig = go.Figure()
    # incline line
    x0, y0 = -2, 0
    x1, y1 = 2, 4 * math.tan(theta) / max(1e-9, math.tan(theta) + 1)
    fig.add_trace(go.Scatter(x=[-2, 2], y=[0, 2 * math.tan(theta)], mode="lines", name="경사면"))
    # block center
    cx, cy = 0.2, 0.2 * math.tan(theta) + 0.35
    fig.add_trace(go.Scatter(x=[cx], y=[cy], mode="markers+text", text=["block"], textposition="top center"))
    # unit vectors along/down slope and normal
    down = (math.cos(theta), math.sin(theta))
    up = (-down[0], -down[1])
    normal = (-math.sin(theta), math.cos(theta))
    _arrow(fig, cx, cy, cx, cy - 1.0, "mg")
    _arrow(fig, cx, cy, cx + normal[0] * 0.9, cy + normal[1] * 0.9, "N")
    if friction:
        d = up if motion_down else down
        _arrow(fig, cx, cy, cx + d[0] * 0.8, cy + d[1] * 0.8, "f")
    _arrow(fig, cx - 1.2, cy - 0.45, cx - 1.2 + down[0] * 0.8, cy - 0.45 + down[1] * 0.8, "+x")
    _arrow(fig, cx - 1.2, cy - 0.45, cx - 1.2 + normal[0] * 0.8, cy - 0.45 + normal[1] * 0.8, "+y")
    fig.update_layout(title="경사면 FBD: 힘 방향과 좌표축", xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False), height=430, margin=dict(l=10, r=10, t=50, b=10), showlegend=False)
    return fig


def pulley_figure() -> Any:
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_shape(type="circle", x0=-0.4, y0=2.6, x1=0.4, y1=3.4)
    fig.add_trace(go.Scatter(x=[-0.25, -0.25, -1.0, -1.0], y=[3, 1.4, 1.4, 0.8], mode="lines", name="줄"))
    fig.add_trace(go.Scatter(x=[0.25, 0.25, 1.0, 1.0], y=[3, 1.4, 1.4, 0.8], mode="lines", name="줄"))
    fig.add_shape(type="rect", x0=-1.25, y0=0.3, x1=-0.75, y1=0.8)
    fig.add_shape(type="rect", x0=0.75, y0=0.3, x1=1.25, y1=0.8)
    fig.add_annotation(x=-1, y=0.55, text="m₁", showarrow=False)
    fig.add_annotation(x=1, y=0.55, text="m₂", showarrow=False)
    _arrow(fig, -1, 0.8, -1, 1.5, "T")
    _arrow(fig, -1, 0.3, -1, -0.45, "m₁g")
    _arrow(fig, 1, 0.8, 1, 1.5, "T")
    _arrow(fig, 1, 0.3, 1, -0.45, "m₂g")
    fig.update_layout(title="도르래: 각 물체의 FBD를 따로 그린다", xaxis=dict(visible=False, range=[-2, 2]), yaxis=dict(visible=False, range=[-0.8, 3.8]), height=430, showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
    return fig


def collision_figure(v1: float, v2: float, m1: float = 2, m2: float = 3) -> Any:
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_shape(type="rect", x0=-2.0, y0=-0.25, x1=-1.4, y1=0.25)
    fig.add_shape(type="rect", x0=1.3, y0=-0.25, x1=2.0, y1=0.25)
    fig.add_annotation(x=-1.7, y=0, text=f"m₁={m1:g}", showarrow=False)
    fig.add_annotation(x=1.65, y=0, text=f"m₂={m2:g}", showarrow=False)
    _arrow(fig, -1.7, 0.45, -1.7 + 0.18 * v1, 0.45, "v₁")
    _arrow(fig, 1.65, 0.45, 1.65 + 0.18 * v2, 0.45, "v₂")
    fig.add_trace(go.Scatter(x=[-2.5, 2.5], y=[-0.3, -0.3], mode="lines"))
    fig.update_layout(title="충돌: 전후 운동량을 벡터 부호와 함께 본다", xaxis=dict(visible=False, range=[-3, 3]), yaxis=dict(visible=False, range=[-1, 1]), height=330, showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
    return fig


def rolling_figure(radius: float, omega: float) -> Any:
    import plotly.graph_objects as go
    r = max(radius, 0.1)
    v = r * omega
    theta = [i * 2 * math.pi / 160 for i in range(161)]
    x = [r * math.cos(t) for t in theta]
    y = [r + r * math.sin(t) for t in theta]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="바퀴"))
    fig.add_trace(go.Scatter(x=[0], y=[r], mode="markers+text", text=["G"], textposition="top center"))
    fig.add_trace(go.Scatter(x=[-2*r, 2*r], y=[0, 0], mode="lines", name="바닥"))
    _arrow(fig, 0, r, min(2*r, v * 0.1), r, "v_G")
    fig.add_annotation(x=0, y=2*r + 0.2, text=f"v_G=rω={v:.2f}", showarrow=False)
    fig.update_layout(title="미끄럼 없는 구름 조건", xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False), height=360, showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
    return fig


def concept_mastery_bar(items: List[Dict[str, Any]]) -> Any:
    import plotly.graph_objects as go
    labels = [x["title"] for x in items]
    vals = [x["mastery"] for x in items]
    fig = go.Figure(data=[go.Bar(x=labels, y=vals)])
    fig.update_layout(title="개념별 숙련도", yaxis=dict(range=[0, 100]), height=420, margin=dict(l=10, r=10, t=50, b=120))
    return fig
