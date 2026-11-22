"""A* grid pathfinding for overworld navigation.

Pure and dependency-light so it unit-tests without an emulator: it takes a
`passable(x, y) -> bool` callable and grid bounds, and returns the list of
button directions ("Up"/"Down"/"Left"/"Right") to walk from start to goal, or
None if unreachable. The caller (walk_to) snapshots passability from the live
tilemap and executes the moves.
"""
import heapq

# GBA screen convention: Up decreases Y (north), Down increases Y (south).
_MOVES = (("Up", 0, -1), ("Down", 0, 1), ("Left", -1, 0), ("Right", 1, 0))


def find_path(start, goal, passable, width, height, max_nodes=8000, ledge=None, edge_ok=None):
    """Shortest 4-connected path from start to goal over passable tiles.

    Returns a list of direction strings, [] if already at goal, or None if no
    path exists (or the search exceeds max_nodes). The goal tile must itself be
    passable. start is assumed reachable/standable (the player is on it).

    `ledge(x, y) -> "Up"/"Down"/"Left"/"Right"/None` optionally identifies one-way
    ledge tiles: a ledge is not standable, but moving INTO it in its facing
    direction hops 2 tiles across (a single D-pad press) to the tile beyond, if
    that landing tile is passable. This lets A* use downhill ledges that plain
    passability treats as walls (the Route 1 top-of-map trap).

    `edge_ok(a, b) -> bool` optionally vetoes a single step between two passable tiles (a bridge deck cannot be entered
    straight from floor: only through its ramps).
    """
    if start == goal:
        return []
    gx, gy = goal
    if not (0 <= gx < width and 0 <= gy < height) or not passable(gx, gy):
        return None

    sx, sy = start
    open_heap = [(abs(sx - gx) + abs(sy - gy), 0, start)]
    came = {start: None}       # node -> (prev, move) ; start maps to None
    best = {start: 0}
    expanded = 0

    while open_heap and expanded < max_nodes:
        _, g, cur = heapq.heappop(open_heap)
        if cur == goal:
            moves = []
            node = cur
            while came[node] is not None:
                prev, mv = came[node]
                moves.append(mv)
                node = prev
            moves.reverse()
            return moves
        if g > best.get(cur, g):
            continue
        expanded += 1
        cx, cy = cur
        for name, dx, dy in _MOVES:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if passable(nx, ny):
                if edge_ok is not None and not edge_ok(cur, (nx, ny)):
                    continue
                step = (nx, ny)
            elif ledge is not None and ledge(nx, ny) == name:
                # Hop the ledge: land two tiles along, must be in-bounds/passable.
                lx, ly = cx + 2 * dx, cy + 2 * dy
                if not (0 <= lx < width and 0 <= ly < height) or not passable(lx, ly):
                    continue
                step = (lx, ly)
            else:
                continue
            ng = g + 1
            if ng < best.get(step, 1 << 30):
                best[step] = ng
                came[step] = (cur, name)
                heapq.heappush(open_heap, (ng + abs(step[0] - gx) + abs(step[1] - gy), ng, step))
    return None


_DELTA = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}


def spin_slide(tile, passable, spin, stops=frozenset()):
    """Where a player who just stepped onto the ARROW tile `tile` ends up. `spin` = {(x, y): direction} for every arrow tile and
    `stops` = the STOP tiles (MB_STOP_SPINNING). Verified live on Rocket Hideout B2F/B3F: the player keeps moving in the direction of
    the last arrow they touched — PLAIN floor does not stop them — turning on each further arrow, until they enter a stop tile (they
    stop on it) or the next tile is blocked (they stop where they are). None = loops forever."""
    cur, d, seen = tile, spin[tile], set()
    while True:
        if (cur, d) in seen:
            return None
        seen.add((cur, d))
        dx, dy = _DELTA[d]
        nxt = (cur[0] + dx, cur[1] + dy)
        if not passable(*nxt):
            return cur
        cur = nxt
        if cur in stops:
            return cur
        if cur in spin:
            d = spin[cur]


def find_path_spin(start, goal, passable, width, height, spin, stops=frozenset(), max_nodes=20000):
    """Shortest path where stepping onto an arrow tile slides the player (see spin_slide). Search nodes are the places the player can
    STAND (a slide's end); each edge is one D-pad press. Returns (moves, stops) — the presses and where each one leaves the player —
    [] / [] when already at the goal, or None when it is unreachable. Replaces find_path on Silph Co. / Rocket Hideout / Viridian Gym."""
    if start == goal:
        return [], []
    gx, gy = goal
    if not (0 <= gx < width and 0 <= gy < height):
        return None
    dist = {start: 0}
    came = {start: None}
    heap = [(0, start)]
    expanded = 0
    while heap:
        d, cur = heapq.heappop(heap)
        if d > dist.get(cur, 1 << 30):
            continue
        if cur == goal:
            moves, ends = [], []
            node = cur
            while came[node] is not None:
                prev, mv = came[node]
                moves.append(mv)
                ends.append(node)
                node = prev
            return moves[::-1], ends[::-1]
        expanded += 1
        if expanded > max_nodes:
            return None
        for name, dx, dy in _MOVES:
            nx, ny = cur[0] + dx, cur[1] + dy
            if not (0 <= nx < width and 0 <= ny < height) or not (passable(nx, ny) or (nx, ny) == goal):
                continue
            end = spin_slide((nx, ny), passable, spin, stops) if (nx, ny) in spin else (nx, ny)
            if end is None:
                continue
            cost = d + abs(end[0] - cur[0]) + abs(end[1] - cur[1])
            if cost < dist.get(end, 1 << 30):
                dist[end] = cost
                came[end] = (cur, name)
                heapq.heappush(heap, (cost, end))
    return None


def door_centers(warps):
    """Collapse contiguous warp tiles (a multi-tile doormat) to the middle tile of
    each cluster — usually the only one that actually warps (side tiles just
    "arrive" without exiting). Single warps pass through unchanged. Pure/testable."""
    clusters = []
    for w in warps:
        for cl in clusters:
            if any(abs(w[0] - x) <= 1 and abs(w[1] - y) <= 1 for x, y in cl):
                cl.append(w)
                break
        else:
            clusters.append([w])
    centers = []
    for cl in clusters:
        mx = sorted(x for x, _ in cl)[len(cl) // 2]
        my = sorted(y for _, y in cl)[len(cl) // 2]
        centers.append(min(cl, key=lambda t: abs(t[0] - mx) + abs(t[1] - my)))
    return centers
