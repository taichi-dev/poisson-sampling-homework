import taichi as ti
import taichi.math as tm

ti.init(arch=ti.cpu)

grid_n = 20
dx = 1 / grid_n
radius = dx * ti.sqrt(2)
desired_samples = 1000
grid = ti.field(dtype=int, shape=(grid_n, grid_n))
samples = ti.Vector.field(2, dtype=float, shape=desired_samples)
window_size = 800
dfield = ti.Vector.field(4, dtype=float, shape=(window_size, window_size))
img = ti.Vector.field(3, dtype=float, shape=(window_size, window_size))
iMouse = ti.Vector.field(2, dtype=float, shape=())
iMouse[None] = [0.5, 0.5]
iResolution = tm.vec2(window_size)


@ti.kernel
def refresh_scene():
    for i, j in dfield:
        dfield[i, j] = tm.vec4(1e5)
        img[i, j] = tm.vec3(1)


@ti.func
def coord_to_index(p):
    return int(p * tm.vec2(grid_n))


@ti.func
def find_nearest_point(p):
    x, y = coord_to_index(p)
    dmin = 1e5
    nearest = iMouse[None]
    for i in range(ti.max(0, x - 2), ti.min(grid_n, x + 3)):
        for j in range(ti.max(0, y - 2), ti.min(grid_n, y + 3)):
            ind = grid[i, j]
            if ind != -1:
                q = samples[ind]
                d = (q - p).norm()
                if d < dmin:
                    dmin = d
                    nearest = q
    return dmin, nearest


@ti.kernel
def poisson_disk_sample(desired_samples: int) -> int:
    samples[0] = (p0 := iMouse[None])
    grid[coord_to_index(p0)]= 0
    head, tail = 0, 1
    while head < tail and head < desired_samples:
        source_x = samples[head]
        head += 1

        for _ in range(100):
            theta = ti.random() * 2 * tm.pi
            offset = tm.vec2(ti.cos(theta), ti.sin(theta)) * (1 + ti.random()) * radius
            new_x = source_x + offset
            new_index = coord_to_index(new_x)

            if 0 <= new_x[0] < 1 and 0 <= new_x[1] < 1:
                collision = (find_nearest_point(new_x)[0] < radius - 1e-6)
                if not collision and tail < desired_samples:
                    samples[tail] = new_x
                    grid[new_index] = tail
                    tail += 1
    return tail


@ti.func
def hash21(p):
    return tm.fract(ti.sin(tm.dot(p, tm.vec2(127.619, 157.583))) * 43758.5453)


@ti.func
def sample_dist(uv):
    uv = uv * iResolution - 0.5
    x, y = tm.clamp(0, iResolution, uv).cast(int)
    return dfield[x, y]


@ti.kernel
def compute_distance_field():
    for i, j in dfield:
        uv = tm.vec2(i, j) / iResolution
        d, p = find_nearest_point(uv)
        d = (uv - p).norm() - radius / 2.
        dfield[i, j] = tm.vec4(d, p.x, p.y, radius / 2.)


@ti.kernel
def render():
    for i, j in img:
        uv = tm.vec2(i, j) / iResolution.y
        st = tm.fract(uv * grid_n) - 0.5
        dg = 0.5 - abs(st)
``
        sf = 2 / iResolution.y
        buf = sample_dist(uv)
        bufSh = sample_dist(uv + tm.vec2(0.005, 0.015))
        col = tm.vec3(1)
        cCol = tm.vec3(hash21(buf.yz + 0.3),  hash21(buf.yz), hash21(buf.yz + 0.09))
        pat = (abs(tm.fract(-buf.x * 150.0) - 0.5) * 2) / 300
        col = tm.mix(col, tm.vec3(0), (1 - tm.smoothstep(0, 3 * sf, pat)) * 0.25)
        ew, ew2 = 0.005, 0.008
        cCol2 = tm.mix(cCol, tm.vec3(1), 0.9)
        col = tm.mix(col, tm.vec3(0),  (1 - tm.smoothstep(0, sf * 2, bufSh.x)) * 0.4)
        col = tm.mix(col, tm.vec3(0),  1 - tm.smoothstep(sf, 0, -buf.x))
        col = tm.mix(col, cCol2,  1 - tm.smoothstep(sf, 0, -buf.x - ew))
        col = tm.mix(col, tm.vec3(0),  1 - tm.smoothstep(sf, 0, -buf.x - ew2 - ew))
        col = tm.mix(col, cCol,  1 - tm.smoothstep(sf, 0., -buf.x - ew2 - ew * 2))
        col = ti.sqrt(max(col, 0))
        img[i, j] = col


grid.fill(-1)

window = ti.GUI("Poisson Disk Sampling", res=window_size, fast_gui=True)
while window.running:
    window.get_event(ti.GUI.PRESS)
    if window.is_pressed(ti.GUI.ESCAPE):
        window.running = False

    if window.is_pressed(ti.GUI.LMB):
        iMouse[None] = window.get_cursor_pos()
        grid.fill(-1)
        refresh_scene()

    if window.is_pressed('p'):
        window.set_image(img)
        window.show('screenshot.png')

    num_samples = poisson_disk_sample(desired_samples)
    compute_distance_field()
    render()
    window.set_image(img)
    window.show()
