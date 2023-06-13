from typing import Optional
import numpy as np

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KarelProg:
    def then(self, s2: "KarelProg") -> "KarelProg":
        return KarelThen(self, s2)


@dataclass(frozen=True)
class KarelRepeat(KarelProg):
    subroutine: KarelProg
    n: int


@dataclass(frozen=True)
class KarelThen(KarelProg):
    s1: KarelProg
    s2: KarelProg


@dataclass(frozen=True)
class KarelAction(KarelProg):
    action: str


@dataclass(frozen=True)
class KarelCond(KarelProg):
    cond: str
    negated: bool = field(default=False)

    def neg(self) -> "KarelCond":
        return KarelCond(self.cond, not self.negated)


@dataclass(frozen=True)
class KarelWhile(KarelProg):
    subroutine: KarelProg
    cond: KarelCond


@dataclass(frozen=True)
class KarelITE(KarelProg):
    cond: KarelCond
    yes: KarelProg
    no: Optional[KarelProg]


class KarelWorld:

    DIRECTION_TOP = 0
    DIRECTION_LEFT = 1
    DIRECTION_BOTTOM = 2
    DIRECTION_RIGHT = 3

    def __init__(self, width: int, height: int) -> None:
        self.grid = np.zeros((width, height))
        self.markers = np.zeros_like(self.grid)
        self.reset()

    def reset(self) -> None:
        self.karel = (0, 0)
        self.current_markers = self.markers.copy()
        self.direction = self.DIRECTION_RIGHT

    def isFrontClear(self) -> bool:
        x, y = self.karel
        width, height = self.grid.shape
        new = self.karel
        if self.direction == self.DIRECTION_BOTTOM:
            new = (x, y + 1)
        elif self.direction == self.DIRECTION_LEFT:
            new = (x - 1, y)
        elif self.direction == self.DIRECTION_TOP:
            new = (x, y - 1)
        else:
            new = (x + 1, y)
        if min(new) < 0 or new[0] >= width or new[1] >= height:
            return False
        return self.grid[new] <= 0

    def act(self, command: str) -> None:
        if command == "move":
            if not self.isFrontClear():
                return
            x, y = self.karel
            if self.direction == self.DIRECTION_BOTTOM:
                self.karel = (x, y + 1)
            elif self.direction == self.DIRECTION_LEFT:
                self.karel = (x - 1, y)
            elif self.direction == self.DIRECTION_TOP:
                self.karel = (x, y - 1)
            else:
                self.karel = (x + 1, y)
        elif command == "turnLeft":
            self.direction -= 1
            if self.direction < 0:
                self.direction = 3
        elif command == "turnRight":
            self.direction += 1
            if self.direction > 3:
                self.direction = 0
        elif command == "putMarker":
            self.current_markers[self.karel] = 1
        elif command == "pickMarker":
            self.current_markers[self.karel] = 0
        else:
            raise Exception(f"invalid command:{command}")

    def eval(self, cond: str) -> bool:
        if cond == "frontIsClear":
            return self.isFrontClear()
        elif cond == "leftIsClear":
            self.act("turnLeft")
            isClear = self.isFrontClear()
            self.act("turnRight")
            return isClear
        elif cond == "rightIsClear":
            self.act("turnRight")
            isClear = self.isFrontClear()
            self.act("turnLeft")
            return isClear
        elif cond == "markersPresent":
            return self.markers[self.karel]
        elif cond == "noMarkersPresent":
            return not self.markers[self.karel]
        raise Exception(f"invalid cond:{cond}")

    def exec(self, prog: KarelProg) -> bool:
        if isinstance(prog, KarelAction):
            self.act(prog.action)
        elif isinstance(prog, KarelCond):
            out = self.eval(prog.cond)
            if prog.negated:
                out = not out
            return out
        elif isinstance(prog, KarelThen):
            self.exec(prog.s1)
            self.exec(prog.s2)
        elif isinstance(prog, KarelRepeat):
            for _ in range(prog.n):
                self.exec(prog.subroutine)
        elif isinstance(prog, KarelWhile):
            while self.exec(prog.cond):
                self.exec(prog.subroutine)
        elif isinstance(prog, KarelITE):
            if self.exec(prog.cond):
                self.exec(prog.yes)
            elif prog.no is not None:
                self.exec(prog.no)
        return False

    def state(self) -> tuple:
        out = self.markers * 2 + self.grid
        out[self.karel] += 4
        return tuple(out)