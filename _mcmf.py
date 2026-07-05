"""
Min-Cost-Max-Flow via Successive Shortest Paths mit Johnson-Potentialen
(Bellman-Ford einmalig zur Initialisierung, danach Dijkstra mit Heap je
Augmentierung). Unterstützt negative Kantenkosten (keine negativen
Zyklen vorausgesetzt -- bei unserem schichtweisen Zuteilungsnetzwerk
garantiert).
"""
import heapq


class MCMF:
    def __init__(self, n: int):
        self.n = n
        self.graph: list[list[int]] = [[] for _ in range(n)]
        self.edges: list[list] = []  # [to, cap_remaining, cost, cap_original]

    def add_edge(self, u: int, v: int, cap: int, cost: float):
        self.graph[u].append(len(self.edges))
        self.edges.append([v, cap, cost, cap])
        self.graph[v].append(len(self.edges))
        self.edges.append([u, 0, -cost, 0])

    def used_flow(self, eid: int) -> int:
        return self.edges[eid][3] - self.edges[eid][1]

    def _bellman_ford(self, s: int):
        n = self.n
        dist = [float("inf")] * n
        dist[s] = 0
        for _ in range(n - 1):
            changed = False
            for u in range(n):
                if dist[u] == float("inf"):
                    continue
                for eid in self.graph[u]:
                    v, cap, cost, _ = self.edges[eid]
                    if cap > 0 and dist[u] + cost < dist[v]:
                        dist[v] = dist[u] + cost
                        changed = True
            if not changed:
                break
        return dist

    def solve(self, s: int, t: int):
        n = self.n
        # Initiale Potentiale per Bellman-Ford (handhabt negative Kosten)
        h = self._bellman_ford(s)
        h = [x if x != float("inf") else 0 for x in h]

        total_flow = 0
        total_cost = 0.0

        while True:
            dist = [float("inf")] * n
            prev_edge = [-1] * n
            dist[s] = 0
            pq = [(0, s)]
            visited = [False] * n
            while pq:
                d, u = heapq.heappop(pq)
                if visited[u]:
                    continue
                visited[u] = True
                for eid in self.graph[u]:
                    v, cap, cost, _ = self.edges[eid]
                    if cap <= 0 or visited[v]:
                        continue
                    reduced = cost + h[u] - h[v]
                    if reduced < -1e-9:
                        continue  # sollte bei korrekten Potentialen nicht vorkommen
                    nd = d + max(reduced, 0)
                    if nd < dist[v]:
                        dist[v] = nd
                        prev_edge[v] = eid
                        heapq.heappush(pq, (nd, v))

            if dist[t] == float("inf"):
                break

            # Potentiale aktualisieren
            for v in range(n):
                if dist[v] < float("inf"):
                    h[v] += dist[v]

            push = float("inf")
            v = t
            while v != s:
                eid = prev_edge[v]
                push = min(push, self.edges[eid][1])
                v = self.edges[eid ^ 1][0]
            v = t
            real_cost_path = 0.0
            while v != s:
                eid = prev_edge[v]
                real_cost_path += self.edges[eid][2]
                self.edges[eid][1] -= push
                self.edges[eid ^ 1][1] += push
                v = self.edges[eid ^ 1][0]

            total_flow += push
            total_cost += push * real_cost_path

        return total_flow, total_cost
