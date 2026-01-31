from math import floor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from collections.abc import Callable, Sequence
if TYPE_CHECKING:
    from python_mpv_jsonipc import MPV


@dataclass(slots=True, frozen=True)
class scrollStyle:
    header: str = "{\\q2\\fs35\\c&00ccff&}"
    comment: str = "{\\q2\\fs30\\c&00ccff&}"
    list: str = "{\\q2\\fs25\\c&Hffffff&}"
    cursor: str = "{\\c&Hfce788&}➤\\h"
    not_selected_prefix: str = "\\h\\h\\h\\h"
    footnote: str = "{\\q2\\fs20\\c&00ccff&}"
    # only used for multiple selections
    selected_multi: str = "{\\c&00ccff&}"

class ScrollList:

    def __init__(
        self,
        MPV_instance: "MPV",
        header: str,
        list_data: Sequence,
        callback: Callable[[int, Sequence], Any] | None = None,
        *,
        comment: str = "",
        repeatable: bool = False,
        style: scrollStyle | None = None,
        max_shown: int = 15,
        footnote: str | None = None
    ) -> None:
        self.style = style or scrollStyle()
        self.header = f"{self.style.header}{header}"
        self.comment = f"{self.style.comment}{comment}\\N\\N" if comment else ""
        self.list_data = list_data
        self.total_entries = len(list_data)
        self.callback = callback if callback else lambda x, y: x
        self.repeatable = repeatable
        self.cursor: int = 0
        self.osd_overlay_list: str = ""
        self.max_shown = max_shown
        self.floor_half_max_shown: int = floor(self.max_shown/2)
        self.mpv = MPV_instance
        self.footnote = footnote
        self.key_bindings: dict[str, Callable] = {
            "UP": self.list_up,
            "DOWN": self.list_down,
            "ENTER": self.select,
            "ESC": self.closeList,
        }
        self.active_key_bindings: list[str] = []
        self.results: Any = None
        self.mpv.command("set_property", f"user-data/python-scroll/{self.mpv.client_name}", "")

    def render(self) -> None:
        self.osd_overlay_list = ""
        distance_from_end = self.total_entries - self.cursor - 1
        if distance_from_end >= self.floor_half_max_shown:
            starting_idx = max(0, self.cursor - self.floor_half_max_shown)
        else:
            starting_idx = max(0, self.total_entries - self.max_shown)
        for i in range(starting_idx, min(starting_idx + self.max_shown, self.total_entries)):
            style_selected = self._get_style(i)
            self.osd_overlay_list += (
                f"{self.style.list}{style_selected}{self.list_data[i]}\\N"
            )
        temp_osd = f"{self.header}\\N\\N{self.comment}{self.osd_overlay_list}{self.style.footnote}\\N\\N"
        if self.footnote is None and self.total_entries > self.max_shown:
            temp_osd += f"({self.cursor+1}/{self.total_entries})"
        elif self.footnote is not None:
            temp_osd += self.footnote
        self.mpv.osd_overlay(6, "ass-events", temp_osd)

    def _get_style(self, index: int) -> str:
        if index == self.cursor:
            return self.style.cursor
        return self.style.not_selected_prefix

    def list_down(self) -> None:
        self.cursor = min(self.cursor + 1, self.total_entries - 1)
        self.render()

    def list_up(self) -> None:
        self.cursor = max(self.cursor - 1, 0)
        self.render()

    def select(self) -> None:
        self.mpv.command("set_property", f"user-data/python-scroll/{self.mpv.client_name}", "y")

    def update(self, header: str, list_data: Sequence, callback: Callable[[int, Sequence], Any] | None = None, *, comment: str = "", repeatable: bool | None = None) -> None:
        self.header = f"{self.style.header}{header}"
        self.comment = f"{self.style.comment}{comment}\\N\\N" if comment else ""
        self.list_data = list_data
        self.total_entries = len(list_data)
        if repeatable is not None:
            self.repeatable = repeatable
        if callback is not None:
            self.callback = callback
        self.cursor = 0
        self.results = None
        self.render()

    def closeList(self) -> None:
        self.mpv.osd_overlay(6, "ass-events", "")
        self.delete_keybindings()
        self.mpv.command("set_property", f"user-data/python-scroll/{self.mpv.client_name}", "n")

    def register_keybindings(self) -> None:
        for key, func in self.key_bindings.items():
            self.active_key_bindings.append(self.mpv.bind_key_press(key, func, repeatable=True, forced=True))

    def delete_keybindings(self) -> None:
        for func in self.active_key_bindings:
            self.mpv.remove_key_binding(func)

    def _callback(self, cursor: int, list_data: Sequence) -> None:
        if self.repeatable:
            self.callback(cursor, list_data)
        else:
            # self.results.append(self.callback(cursor, list_data))
            self.results = self.callback(cursor, list_data)

    def get_selection(self) -> Any:
        self.register_keybindings()
        self.render()

        while True:
            self.mpv.wait_for_property(f"user-data/python-scroll/{self.mpv.client_name}")
            temp_selection = self.mpv.command(
                "get_property", f"user-data/python-scroll/{self.mpv.client_name}"
            )
            self.mpv.command("set_property", f"user-data/python-scroll/{self.mpv.client_name}", "")
            if temp_selection == "y":
                self._callback(self.cursor, self.list_data)
            elif temp_selection == "n":
                return None
            else:
                break
            if not self.repeatable:
                break
            self.render()

        self.mpv.osd_overlay(6, "ass-events", "")
        self.delete_keybindings()

        return self.results


class MultipleSelection(ScrollList):
    def __init__(
        self,
        MPV_instance: "MPV",
        header: str,
        list_data: Sequence,
        *,
        comment: str = "",
        style: scrollStyle | None = None,
        max_shown: int = 15
    ) -> None:
        super().__init__(
            MPV_instance,
            header,
            list_data,
            comment = comment,
            callback=None,
            repeatable=True,
            style = style,
            max_shown=max_shown
        )
        self.results = []
        self.key_bindings["TAB"] = self.confirmSelection
        self.active_key_bindings.append(self.mpv.bind_key_press("TAB", self.confirmSelection, forced=True))

    def _callback(self, cursor: int, list_data: Sequence) -> None:
        if cursor not in self.results:
            self.results.append(cursor)
        else:
            self.results.remove(cursor)

    def _get_style(self, index: int) -> str:
        if index not in self.results:
            return super()._get_style(index)

        if index == self.cursor:
            tmp_style = self.style.cursor
        else:
            tmp_style = self.style.not_selected_prefix + self.style.selected_multi

        tmp_style += "X\\h"
        return tmp_style

    def confirmSelection(self) -> None:
        self.mpv.command("set_property", f"user-data/python-scroll/{self.mpv.client_name}", "confirmed")
