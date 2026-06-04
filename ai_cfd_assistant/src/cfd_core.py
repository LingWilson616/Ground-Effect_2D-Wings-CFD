"""CFD core: NACA airfoil generation + 2D panel method."""

from dataclasses import dataclass
import numpy as np
from scipy.interpolate import interp1d


@dataclass
class AirfoilResult:
    x: np.ndarray         # x coordinates
    y: np.ndarray         # y coordinates (upper + lower)
    xu: np.ndarray        # upper surface x
    yu: np.ndarray        # upper surface y
    xl: np.ndarray        # lower surface x
    yl: np.ndarray        # lower surface y
    camber: np.ndarray    # camber line y
    naca_code: str        # e.g. "2412"


def naca4(code: str, n: int = 160) -> AirfoilResult:
    """Generate NACA 4-digit airfoil coordinates.

    Parameters:
        code: 4-digit NACA code as string (e.g. '2412')
        n: number of points (half cosine spacing)
    """
    m = int(code[0]) / 100.0    # max camber
    p = int(code[1]) / 10.0     # position of max camber
    t = int(code[2:]) / 100.0   # max thickness

    # cosine spacing (clustered at LE and TE)
    beta = np.linspace(0, np.pi, n // 2)
    x = (1 - np.cos(beta)) / 2

    # thickness distribution
    a0, a1, a2, a3, a4 = 0.2969, -0.1260, -0.3516, 0.2843, -0.1015
    yt = (t / 0.2) * (a0 * np.sqrt(x) + a1 * x + a2 * x ** 2 + a3 * x ** 3 + a4 * x ** 4)

    # camber line (handle symmetric airfoils where m=0 or p=0)
    if m < 1e-12 or p < 1e-12:
        yc = np.zeros_like(x)
        dyc = np.zeros_like(x)
    else:
        yc = np.where(
            x < p,
            m / p ** 2 * (2 * p * x - x ** 2),
            m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x ** 2)
        )
        dyc = np.where(
            x < p,
            2 * m / p ** 2 * (p - x),
            2 * m / (1 - p) ** 2 * (p - x)
        )

    theta = np.arctan(dyc)
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    return AirfoilResult(
        x=np.concatenate([xu, xl[::-1]]),
        y=np.concatenate([yu, yl[::-1]]),
        xu=xu, yu=yu, xl=xl, yl=yl,
        camber=yc, naca_code=code,
    )


def naca5(code: str, n: int = 160) -> AirfoilResult:
    """Generate NACA 5-digit airfoil (simplified)."""
    # Simplified 5-digit implementation
    cl_design = int(code[0]) * 0.15
    p = int(code[1]) / 20.0
    t = int(code[2:]) / 100.0

    beta = np.linspace(0, np.pi, n // 2)
    x = (1 - np.cos(beta)) / 2

    a0, a1, a2, a3, a4 = 0.2969, -0.1260, -0.3516, 0.2843, -0.1015
    yt = (t / 0.2) * (a0 * np.sqrt(x) + a1 * x + a2 * x ** 2 + a3 * x ** 3 + a4 * x ** 4)

    # Simplified camber for 5-digit
    yc = np.where(
        x < p,
        cl_design / (2 * np.pi) * (x - x ** 2 / (2 * p)),
        cl_design / (2 * np.pi) * ((p / 2) + (x - p) * (1 - x) / (2 * (1 - p)))
    )

    dyc = np.where(
        x < p,
        cl_design / (2 * np.pi) * (1 - x / p),
        cl_design / (2 * np.pi) * ((1 - x) / (1 - p) - (x - p) / (2 * (1 - p)))
    )

    theta = np.arctan(dyc)
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    return AirfoilResult(
        x=np.concatenate([xu, xl[::-1]]),
        y=np.concatenate([yu, yl[::-1]]),
        xu=xu, yu=yu, xl=xl, yl=yl,
        camber=yc, naca_code=code,
    )


@dataclass
class PanelMethodResult:
    cp: np.ndarray         # pressure coefficient on each panel
    cl: float              # lift coefficient
    cpm: float             # pitching moment coefficient
    x_panel: np.ndarray   # panel center x
    y_panel: np.ndarray   # panel center y
    u_e: np.ndarray       # external velocity / freestream
    stagnation_pt: tuple  # stagnation point (x, y)


def _panel_influence(xc, yc, nx, ny, xj1, yj1, xj2, yj2, phi_j, S_j):
    """Compute influence of panel j (from node j→j+1) on point (xc, yc).

    Returns (u_source, w_source, u_vortex, w_vortex) — induced velocity
    from unit source and unit vortex on panel j.
    """
    # Transform control point to panel j's local frame
    x1 = (xc - xj1) * np.cos(phi_j) + (yc - yj1) * np.sin(phi_j)
    y1 = -(xc - xj1) * np.sin(phi_j) + (yc - yj1) * np.cos(phi_j)
    x2 = (xc - xj2) * np.cos(phi_j) + (yc - yj2) * np.sin(phi_j)
    y2 = -(xc - xj2) * np.sin(phi_j) + (yc - yj2) * np.cos(phi_j)

    r1 = np.sqrt(x1**2 + y1**2)
    r2 = np.sqrt(x2**2 + y2**2)
    eps = 1e-12

    if r1 < eps or r2 < eps:
        return 0.0, 0.0, 0.0, 0.0

    theta1 = np.arctan2(y1, x1)
    theta2 = np.arctan2(y2, x2)

    # Source influence in local frame
    if abs(y1) < eps and abs(y2) < eps:
        ul_source = 0.0
        wl_source = 0.0
    else:
        ul_source = (1 / (2 * np.pi)) * np.log(r2 / r1)
        wl_source = (1 / (2 * np.pi)) * (theta2 - theta1)

    # Vortex influence in local frame
    if abs(y1) < eps and abs(y2) < eps:
        ul_vortex = 0.0
        wl_vortex = 0.0
    else:
        ul_vortex = -(1 / (2 * np.pi)) * (theta2 - theta1)
        wl_vortex = (1 / (2 * np.pi)) * np.log(r2 / r1)

    # Rotate back to global frame
    u_source = ul_source * np.cos(phi_j) - wl_source * np.sin(phi_j)
    w_source = ul_source * np.sin(phi_j) + wl_source * np.cos(phi_j)
    u_vortex = ul_vortex * np.cos(phi_j) - wl_vortex * np.sin(phi_j)
    w_vortex = ul_vortex * np.sin(phi_j) + wl_vortex * np.cos(phi_j)

    return u_source, w_source, u_vortex, w_vortex


def panel_method(airfoil: AirfoilResult, alpha: float = 0.0, n_panels: int = 100) -> PanelMethodResult:
    """2D source + vortex panel method (Hess & Smith style).

    Parameters:
        airfoil: AirfoilResult from naca4/naca5
        alpha: angle of attack in degrees
        n_panels: number of panels
    """
    # Get raw airfoil as closed loop (TE → upper → LE → lower → TE)
    xu, yu = airfoil.xu, airfoil.yu
    xl, yl = airfoil.xl, airfoil.yl

    # Build closed polygon: TE→upper surface→LE→lower surface→TE
    # xu goes from LE (0) to TE (1), xl goes from LE (0) to TE (1)
    x_nodes = np.concatenate([xu[::-1], xl[1:]])  # upper reversed (TE→LE), lower (LE→TE)
    y_nodes = np.concatenate([yu[::-1], yl[1:]])

    n_total = len(x_nodes)
    if n_total < n_panels + 1:
        n_panels = n_total - 1

    # Subsample
    indices = np.linspace(0, n_total - 1, n_panels + 1, dtype=int)
    x_nodes = x_nodes[indices]
    y_nodes = y_nodes[indices]
    n_panels = len(x_nodes) - 1

    # Panel geometry
    xc = np.zeros(n_panels)
    yc = np.zeros(n_panels)
    S = np.zeros(n_panels)
    phi = np.zeros(n_panels)
    nx = np.zeros(n_panels)
    ny = np.zeros(n_panels)

    for i in range(n_panels):
        j = i + 1
        xc[i] = (x_nodes[i] + x_nodes[j]) / 2
        yc[i] = (y_nodes[i] + y_nodes[j]) / 2
        dx = x_nodes[j] - x_nodes[i]
        dy = y_nodes[j] - y_nodes[i]
        S[i] = np.sqrt(dx**2 + dy**2)
        phi[i] = np.arctan2(dy, dx)
        nx[i] = dy / S[i]
        ny[i] = -dx / S[i]

    # Freestream
    alpha_rad = np.radians(alpha)
    u_inf = np.cos(alpha_rad)
    w_inf = np.sin(alpha_rad)

    # Build influence matrix A of size (n+1)×(n+1)
    N = n_panels + 1
    A = np.zeros((N, N))
    b = np.zeros(N)

    # Fill influence coefficients
    for i in range(n_panels):
        # RHS: -V∞·n
        b[i] = -(u_inf * nx[i] + w_inf * ny[i])

        for j in range(n_panels):
            us, ws, uv, wv = _panel_influence(
                xc[i], yc[i], nx[i], ny[i],
                x_nodes[j], y_nodes[j], x_nodes[j + 1], y_nodes[j + 1],
                phi[j], S[j]
            )
            # Normal component: (u,w)·n
            A[i, j] = us * nx[i] + ws * ny[i]
            A[i, n_panels] += uv * nx[i] + wv * ny[i]

    # Kutta condition: sum of tangential velocities at TE panels = 0
    # Last row: use panels near TE (first and last panels)
    i_upper_te = 0        # First panel (TE on upper side)
    i_lower_te = n_panels - 1  # Last panel (TE on lower side)

    A[n_panels, :] = 0.0
    for j in range(n_panels):
        # Tangential influence on upper TE panel
        us_u, ws_u, uv_u, wv_u = _panel_influence(
            xc[i_upper_te], yc[i_upper_te], np.cos(phi[i_upper_te]), np.sin(phi[i_upper_te]),
            x_nodes[j], y_nodes[j], x_nodes[j + 1], y_nodes[j + 1],
            phi[j], S[j]
        )
        ut_source_u = us_u * np.cos(phi[i_upper_te]) + ws_u * np.sin(phi[i_upper_te])
        ut_vortex_u = uv_u * np.cos(phi[i_upper_te]) + wv_u * np.sin(phi[i_upper_te])

        # Tangential influence on lower TE panel
        us_l, ws_l, uv_l, wv_l = _panel_influence(
            xc[i_lower_te], yc[i_lower_te], np.cos(phi[i_lower_te]), np.sin(phi[i_lower_te]),
            x_nodes[j], y_nodes[j], x_nodes[j + 1], y_nodes[j + 1],
            phi[j], S[j]
        )
        ut_source_l = us_l * np.cos(phi[i_lower_te]) + ws_l * np.sin(phi[i_lower_te])
        ut_vortex_l = uv_l * np.cos(phi[i_lower_te]) + wv_l * np.sin(phi[i_lower_te])

        A[n_panels, j] = ut_source_u + ut_source_l
        A[n_panels, n_panels] += ut_vortex_u + ut_vortex_l

    # Kutta RHS
    ut_inf_u = -(u_inf * np.cos(phi[i_upper_te]) + w_inf * np.sin(phi[i_upper_te]))
    ut_inf_l = -(u_inf * np.cos(phi[i_lower_te]) + w_inf * np.sin(phi[i_lower_te]))
    b[n_panels] = ut_inf_u + ut_inf_l

    # Solve
    try:
        solution = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        solution = np.linalg.lstsq(A, b, rcond=None)[0]

    sigma = solution[:n_panels]
    gamma = solution[n_panels]

    # Compute tangential velocity and Cp on each panel
    vt = np.zeros(n_panels)
    for i in range(n_panels):
        vt[i] = u_inf * np.cos(phi[i]) + w_inf * np.sin(phi[i])
        for j in range(n_panels):
            us, ws, uv, wv = _panel_influence(
                xc[i], yc[i], nx[i], ny[i],
                x_nodes[j], y_nodes[j], x_nodes[j + 1], y_nodes[j + 1],
                phi[j], S[j]
            )
            ut_source = us * np.cos(phi[i]) + ws * np.sin(phi[i])
            ut_vortex = uv * np.cos(phi[i]) + wv * np.sin(phi[i])
            vt[i] += sigma[j] * ut_source + gamma * ut_vortex

        # Self-induced tangential velocity (source panel: vt = 0 for self, vortex: γ/2)
        vt[i] += gamma / 2.0

    cp = 1.0 - vt**2

    # Lift from Kutta-Joukowski (circulation)
    cl = 2.0 * gamma * np.sum(S)

    # Pitching moment about quarter chord
    cm = 0.0
    for i in range(n_panels):
        cm -= cp[i] * S[i] * (xc[i] - 0.25) * ny[i]
    cm = cm * np.cos(alpha_rad)

    # Stagnation point
    stag_idx = np.argmin(np.abs(vt))
    stag_pt = (float(xc[stag_idx]), float(yc[stag_idx]))

    return PanelMethodResult(
        cp=cp, cl=cl, cpm=cm,
        x_panel=xc, y_panel=yc, u_e=vt,
        stagnation_pt=stag_pt,
    )


def compute_streamlines(
    airfoil: AirfoilResult,
    result: PanelMethodResult,
    alpha: float = 0.0,
    n_streamlines: int = 20,
    n_steps: int = 200,
    step_size: float = 0.02,
) -> list:
    """Compute streamlines using RK2 integration of velocity field."""
    alpha_rad = np.radians(alpha)
    u_inf = np.cos(alpha_rad)
    w_inf = np.sin(alpha_rad)

    x_min, x_max = -0.5, 2.0
    y_min, y_max = -1.0, 1.0

    # Starting points for streamlines (upstream rake)
    x_start = x_min
    y_starts = np.linspace(y_min, y_max, n_streamlines)

    # Build velocity field interpolator
    sigma = np.zeros(len(result.x_panel))  # We need to recompute or cache
    gamma_val = result.cl / (-2.0 * np.sum(np.sqrt(
        np.diff(np.append(airfoil.x, airfoil.x[0])) ** 2 +
        np.diff(np.append(airfoil.y, airfoil.y[0])) ** 2
    )))

    def velocity_at(px, py):
        """Induced velocity at point (px, py)."""
        u_ind, w_ind = 0.0, 0.0
        # Simplified: uniform flow + vortex at quarter chord
        # Vortex influence
        x_vortex, y_vortex = 0.25, 0.0
        dx = px - x_vortex
        dy = py - y_vortex
        r2 = dx ** 2 + dy ** 2 + 1e-12
        circ = gamma_val
        u_ind += circ / (2 * np.pi) * dy / r2
        w_ind += -circ / (2 * np.pi) * dx / r2
        return u_inf + u_ind, w_inf + w_ind

    streamlines = []
    for y0 in y_starts:
        path = [(x_start, y0)]
        x, y = x_start, y0
        for _ in range(n_steps):
            if x > x_max or x < x_min or y > y_max or y < y_min:
                break
            k1_u, k1_w = velocity_at(x, y)
            h_half = step_size / 2
            k2_u, k2_w = velocity_at(x + h_half * k1_u, y + h_half * k1_w)
            x += step_size * k2_u
            y += step_size * k2_w
            path.append((x, y))
        streamlines.append(np.array(path))

    return streamlines
