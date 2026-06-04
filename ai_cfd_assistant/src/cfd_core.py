"""CFD core: NACA airfoil generation + 2D panel method (Hess & Smith).

Physical defaults: V∞=16.6 m/s, ρ=1.225 kg/m³ (standard sea-level air).
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class AirfoilResult:
    x: np.ndarray
    y: np.ndarray
    xu: np.ndarray
    yu: np.ndarray
    xl: np.ndarray
    yl: np.ndarray
    camber: np.ndarray
    naca_code: str


@dataclass
class PanelMethodResult:
    cp: np.ndarray
    cl: float
    cd: float
    cm: float
    x_panel: np.ndarray
    y_panel: np.ndarray
    u_e: np.ndarray
    stagnation_pt: tuple
    chord_m: float = 1.0
    v_inf: float = 16.6
    rho: float = 1.225
    lift_per_span: float = 0.0
    downforce_per_span: float = 0.0

    @property
    def cpm(self):
        return self.cm


def naca4(code: str, n: int = 160) -> AirfoilResult:
    m = int(code[0]) / 100.0
    p = int(code[1]) / 10.0
    t = int(code[2:]) / 100.0

    beta = np.linspace(0, np.pi, n // 2)
    x = (1 - np.cos(beta)) / 2

    a0, a1, a2, a3, a4 = 0.2969, -0.1260, -0.3516, 0.2843, -0.1015
    yt = (t / 0.2) * (a0*np.sqrt(x) + a1*x + a2*x**2 + a3*x**3 + a4*x**4)

    if m < 1e-12 or p < 1e-12:
        yc = np.zeros_like(x)
        dyc = np.zeros_like(x)
    else:
        yc = np.where(x < p,
            m/p**2 * (2*p*x - x**2),
            m/(1-p)**2 * ((1-2*p) + 2*p*x - x**2))
        dyc = np.where(x < p,
            2*m/p**2 * (p - x),
            2*m/(1-p)**2 * (p - x))

    theta = np.arctan(dyc)
    xu = x - yt*np.sin(theta)
    yu = yc + yt*np.cos(theta)
    xl = x + yt*np.sin(theta)
    yl = yc - yt*np.cos(theta)

    return AirfoilResult(
        x=np.concatenate([xu, xl[::-1]]),
        y=np.concatenate([yu, yl[::-1]]),
        xu=xu, yu=yu, xl=xl, yl=yl,
        camber=yc, naca_code=code,
    )


def naca5(code: str, n: int = 160) -> AirfoilResult:
    cl_design = int(code[0]) * 0.15
    p = int(code[1]) / 20.0
    t = int(code[2:]) / 100.0

    beta = np.linspace(0, np.pi, n // 2)
    x = (1 - np.cos(beta)) / 2

    a0, a1, a2, a3, a4 = 0.2969, -0.1260, -0.3516, 0.2843, -0.1015
    yt = (t/0.2) * (a0*np.sqrt(x) + a1*x + a2*x**2 + a3*x**3 + a4*x**4)

    if abs(p) < 1e-12:
        yc = np.zeros_like(x)
        dyc = np.zeros_like(x)
    else:
        yc = np.where(x < p,
            cl_design/(2*np.pi) * (x - x**2/(2*p)),
            cl_design/(2*np.pi) * (p/2 + (x-p)*(1-x)/(2*(1-p))))
        dyc = np.where(x < p,
            cl_design/(2*np.pi) * (1 - x/p),
            cl_design/(2*np.pi) * ((1-x)/(1-p) - (x-p)/(2*(1-p))))

    theta = np.arctan(dyc)
    xu = x - yt*np.sin(theta)
    yu = yc + yt*np.cos(theta)
    xl = x + yt*np.sin(theta)
    yl = yc - yt*np.cos(theta)

    return AirfoilResult(
        x=np.concatenate([xu, xl[::-1]]),
        y=np.concatenate([yu, yl[::-1]]),
        xu=xu, yu=yu, xl=xl, yl=yl,
        camber=yc, naca_code=code,
    )


def _source_normal_influence(xc, yc, xn, yn, xj, yj, xjp1, yjp1):
    """Normal velocity induced at (xc,yc) by unit source on panel [j, j+1], dotted with (xn,yn)."""
    dxj, dyj = xjp1 - xj, yjp1 - yj
    sj = np.sqrt(dxj**2 + dyj**2)
    cb, sb = dxj/sj, dyj/sj

    xi  =  (xc-xj)*cb + (yc-yj)*sb
    eta = -(xc-xj)*sb + (yc-yj)*cb
    xi2 =  (xc-xjp1)*cb + (yc-yjp1)*sb

    eps = 1e-10
    theta1 = np.arctan2(eta, xi + eps)
    theta2 = np.arctan2(eta, xi2 + eps)
    dtheta = theta2 - theta1

    u = -dtheta * sb / (2*np.pi)
    w =  dtheta * cb / (2*np.pi)
    return u*xn + w*yn


def _source_tangent_influence(xc, yc, xt, yt, xj, yj, xjp1, yjp1):
    """Tangential velocity induced at (xc,yc) by unit source on panel [j, j+1], dotted with (xt,yt)."""
    dxj, dyj = xjp1 - xj, yjp1 - yj
    sj = np.sqrt(dxj**2 + dyj**2)
    cb, sb = dxj/sj, dyj/sj

    xi  =  (xc-xj)*cb + (yc-yj)*sb
    eta = -(xc-xj)*sb + (yc-yj)*cb
    xi2 =  (xc-xjp1)*cb + (yc-yjp1)*sb

    eps = 1e-10
    r1 = np.sqrt(xi**2 + eta**2 + eps)
    r2 = np.sqrt(xi2**2 + eta**2 + eps)
    dlnr = np.log(max(r2, eps)) - np.log(max(r1, eps))

    u = -dlnr * cb / (2*np.pi)
    w = -dlnr * sb / (2*np.pi)
    return u*xt + w*yt


def _vortex_normal_influence(xc, yc, xn, yn, xj, yj, xjp1, yjp1):
    """Normal velocity from unit vortex on panel [j, j+1], dotted with (xn,yn)."""
    dxj, dyj = xjp1 - xj, yjp1 - yj
    sj = np.sqrt(dxj**2 + dyj**2)
    cb, sb = dxj/sj, dyj/sj

    xi  =  (xc-xj)*cb + (yc-yj)*sb
    eta = -(xc-xj)*sb + (yc-yj)*cb
    xi2 =  (xc-xjp1)*cb + (yc-yjp1)*sb

    eps = 1e-10
    r1 = np.sqrt(xi**2 + eta**2 + eps)
    r2 = np.sqrt(xi2**2 + eta**2 + eps)
    dlnr = np.log(max(r2, eps)) - np.log(max(r1, eps))

    u = dlnr * cb / (2*np.pi)
    w = dlnr * sb / (2*np.pi)
    return u*xn + w*yn


def panel_method(airfoil: AirfoilResult, alpha: float = 0.0, n_panels: int = 100,
                 v_inf: float = 16.6, rho: float = 1.225) -> PanelMethodResult:
    """2D source+vortex panel method (Hess & Smith, 1966).

    N source panels + 1 global vortex strength. N normal BCs + 1 Kutta condition.
    """
    # Build closed polygon: TE→upper→LE→lower→TE (clockwise)
    xu, yu = airfoil.xu, airfoil.yu
    xl, yl = airfoil.xl, airfoil.yl
    # Force TE closure: average upper/lower TE to same point
    te_x = (xu[-1] + xl[-1]) / 2
    te_y = (yu[-1] + yl[-1]) / 2
    xu_c = xu.copy(); yu_c = yu.copy()
    xl_c = xl.copy(); yl_c = yl.copy()
    xu_c[-1] = te_x; yu_c[-1] = te_y
    xl_c[-1] = te_x; yl_c[-1] = te_y
    x_raw = np.concatenate([xu_c[::-1], xl_c[1:]])
    y_raw = np.concatenate([yu_c[::-1], yl_c[1:]])

    # Subsample
    nr = len(x_raw)
    if nr > n_panels + 1:
        idx = np.linspace(0, nr-1, n_panels+1, dtype=int)
        x_raw = x_raw[idx]
        y_raw = y_raw[idx]
    n = len(x_raw) - 1  # actual panels

    # Panel geometry
    xc = np.zeros(n); yc = np.zeros(n); S = np.zeros(n)
    nx = np.zeros(n); ny = np.zeros(n); tx = np.zeros(n); ty = np.zeros(n)
    for i in range(n):
        j = i + 1
        xc[i] = (x_raw[i] + x_raw[j]) / 2
        yc[i] = (y_raw[i] + y_raw[j]) / 2
        dx = x_raw[j] - x_raw[i]
        dy = y_raw[j] - y_raw[i]
        S[i] = np.sqrt(dx**2 + dy**2)
        nx[i] =  dy / S[i]
        ny[i] = -dx / S[i]
        tx[i] =  dx / S[i]
        ty[i] =  dy / S[i]

    # Freestream
    a = np.radians(alpha)
    u0, w0 = np.cos(a), np.sin(a)

    # System: [n sources, 1 vortex] × [n+1 equations]
    A = np.zeros((n+1, n+1))
    b = np.zeros(n+1)

    # Normal BC rows — only sources (vortex normal integrates to 0 on closed body)
    for i in range(n):
        b[i] = -(u0*nx[i] + w0*ny[i])
        for j in range(n):
            A[i, j] = _source_normal_influence(xc[i], yc[i], nx[i], ny[i],
                                                x_raw[j], y_raw[j], x_raw[j+1], y_raw[j+1])
        A[i, n] = 0.0  # uniform vortex → zero normal velocity on closed body

    # Kutta condition row
    iu, il = 0, n-1
    b[n] = -(u0*tx[iu] + w0*ty[iu]) - (u0*tx[il] + w0*ty[il])
    for j in range(n):
        vu = _source_tangent_influence(xc[iu], yc[iu], tx[iu], ty[iu],
                                        x_raw[j], y_raw[j], x_raw[j+1], y_raw[j+1])
        vl = _source_tangent_influence(xc[il], yc[il], tx[il], ty[il],
                                        x_raw[j], y_raw[j], x_raw[j+1], y_raw[j+1])
        A[n, j] = vu + vl
    A[n, n] = 1.0  # vortex: γ/2 + γ/2 = γ at TE (tangents oppose, flip sign)

    # Solve
    try:
        sol = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        sol = np.linalg.lstsq(A, b, rcond=None)[0]

    sigma = sol[:n]
    gamma = sol[n]

    # Tangential velocity on each panel
    vt = np.zeros(n)
    for i in range(n):
        vt[i] = u0*tx[i] + w0*ty[i]
        for j in range(n):
            vt[i] += sigma[j] * _source_tangent_influence(xc[i], yc[i], tx[i], ty[i],
                                                           x_raw[j], y_raw[j], x_raw[j+1], y_raw[j+1])
        vt[i] += gamma * 0.5  # vortex self-induction

    cp = 1.0 - vt**2

    # CL from pressure integration
    cl_pressure = 0.0
    cd_pressure = 0.0
    for i in range(n):
        fx = -cp[i] * S[i] * nx[i]
        fy = -cp[i] * S[i] * ny[i]
        cl_pressure += fy * np.cos(a) - fx * np.sin(a)
        cd_pressure += fy * np.sin(a) + fx * np.cos(a)
    cl = cl_pressure

    # CL from circulation (K-J) for comparison
    cl_circ = 2.0 * gamma * np.sum(S)  # 2*Γ / (V∞*c), V∞=1, c=1

    # Pitching moment about quarter-chord
    cm = 0.0
    for i in range(n):
        cm -= cp[i] * S[i] * ((xc[i]-0.25)*ny[i] - yc[i]*nx[i])
    cm = cm * np.cos(a)

    # Stagnation point
    si = np.argmin(np.abs(vt))
    stag = (float(xc[si]), float(yc[si]))

    # Physical
    q = 0.5 * rho * v_inf**2
    lift = q * cl * 1.0
    downforce = -lift

    return PanelMethodResult(
        cp=cp, cl=cl, cd=0.0, cm=cm,
        x_panel=xc, y_panel=yc, u_e=vt,
        stagnation_pt=stag,
        v_inf=v_inf, rho=rho,
        lift_per_span=lift, downforce_per_span=downforce,
    )


def compute_streamlines(airfoil: AirfoilResult, result: PanelMethodResult,
                        alpha: float = 0.0, n_streamlines: int = 20,
                        n_steps: int = 150, step_size: float = 0.015) -> list:
    """Simple vortex+uniform-flow streamline tracer."""
    alpha_rad = np.radians(alpha)
    u_inf = np.cos(alpha_rad)
    w_inf = np.sin(alpha_rad)
    gamma_val = result.cl / (-2.0 * np.sum(np.sqrt(
        np.diff(np.append(airfoil.x, airfoil.x[0]))**2 +
        np.diff(np.append(airfoil.y, airfoil.y[0]))**2)))

    def vel(px, py):
        dx = px - 0.25
        dy = py
        r2 = dx**2 + dy**2 + 1e-12
        ui = gamma_val/(2*np.pi) * dy/r2
        wi = -gamma_val/(2*np.pi) * dx/r2
        return u_inf + ui, w_inf + wi

    streamlines = []
    for y0 in np.linspace(-0.8, 0.8, n_streamlines):
        path = [(-0.3, y0)]
        x, y = -0.3, y0
        for _ in range(n_steps):
            if x > 2.0 or x < -0.5 or abs(y) > 1.2:
                break
            u, w = vel(x, y)
            x += step_size * u
            y += step_size * w
            path.append((x, y))
        streamlines.append(np.array(path))
    return streamlines
