import curses
import queue

def display_intro(stdscr: curses.window):
    """
    Display the introductory message in the ncurses window.

    Args:
        stdscr (curses.window): The ncurses window object.
    """
    intro_text = (
        "Welcome to the Real-Time Audio Translator!\n\n"
        "This software allows you to select one or more audio inputs and translate "
        "the audio from one language to another in real-time.\n\n"
        "You will be prompted to select the audio inputs and specify the language "
        "for each input.\n\n"
        "Example language codes:\n"
        "en (English), es (Spanish), zh (Chinese), hi (Hindi),\n"
        "ar (Arabic), fr (French), ru (Russian), pt (Portuguese),\n"
        "bn (Bengali), ja (Japanese)\n\n"
    )
    stdscr.clear()
    stdscr.addstr(0, 0, intro_text)
    stdscr.refresh()

def wrap_text(text: str, width: int, start_pos: int = 0) -> list[str]:
    """
    Wrap text to fit within a specified width.

    Args:
        text (str): The text to wrap.
        width (int): The width to wrap the text to.
        start_pos (int): The starting position for wrapping.

    Returns:
        list[str]: A list of strings, each representing a line of wrapped text.
    """
    lines = []
    for paragraph in text.splitlines():
        while len(paragraph) > width or (len(lines) == 0 and start_pos > 0 and len(paragraph) > width - start_pos):
            if len(lines) == 0 and start_pos > 0:
                space_pos = paragraph.rfind(' ', 0, width - start_pos)
                if space_pos == -1:
                    space_pos = 0
            else:
                space_pos = paragraph.rfind(' ', 0, width)
                if space_pos == -1:
                    space_pos = width
            lines.append(paragraph[:space_pos])
            paragraph = paragraph[space_pos:].lstrip()
        if len(paragraph) > 0:
            lines.append(paragraph)
    return lines

def writer_thread(stdscr: curses.window, message_queue: queue.Queue):
    """
    Continuously retrieves messages from the queue and displays them in the terminal window.

    Args:
        stdscr (curses.window): The curses window object.
        message_queue (queue.Queue): Queue from which messages are retrieved.
    """
    stdscr.scrollok(True)
    y_pos_left = 0
    y_pos_right = 0
    last_left_label = None
    last_right_label = None
    last_left_x_offset = 0
    last_right_x_offset = 0

    while True:
        try:
            label, text, side = message_queue.get()

            height, width = stdscr.getmaxyx()
            mid_x = width // 2

            y_pos = 0
            x_pos = 0
            last_x_offset = 0

            if side == "left":
                if last_left_label != label:
                    last_left_label = label
                    if y_pos_left > 0:
                        y_pos_left += 2
                    stdscr.addstr(y_pos_left, 0, f"{label}:", curses.A_BOLD)
                    stdscr.refresh()
                    y_pos_left += 1
                else:
                    last_x_offset = last_left_x_offset
                y_pos = y_pos_left
                x_pos = 0
                wrapped_lines = wrap_text(text, mid_x - 1, last_x_offset)
                last_left_x_offset = len(wrapped_lines[-1]) if wrapped_lines else 0
            else:
                if last_right_label != label:
                    last_right_label = label
                    if y_pos_right > 0:
                        y_pos_right += 2
                    stdscr.addstr(y_pos_right, mid_x + 1, f"{label}:", curses.A_BOLD)
                    stdscr.refresh()
                    y_pos_right += 1
                else:
                    last_x_offset = last_right_x_offset
                y_pos = y_pos_right
                x_pos = mid_x + 1
                wrapped_lines = wrap_text(text, width - mid_x - 1, last_x_offset)
                last_right_x_offset = len(wrapped_lines[-1]) if wrapped_lines else 0


            for i, line in enumerate(wrapped_lines):
                if i > 0:
                  y_pos += 1
                # Adjust the position if the output would exceed the terminal height
                while y_pos >= height:
                    stdscr.scroll()
                    y_pos -= 1
                stdscr.addstr(y_pos, x_pos + last_x_offset if i == 0 else x_pos, line)
                stdscr.refresh()
                last_x_offset = len(line) + last_x_offset if i == 0 else len(line)

            if side == "left":
                y_pos_left = y_pos
                last_left_x_offset = min(last_x_offset + 1, mid_x - 1)
            else:
                y_pos_right = y_pos
                last_right_x_offset = min(last_x_offset + 1, mid_x - 1)
                if y_pos_right > y_pos_left:
                    y_pos_left = y_pos_right
                    last_left_x_offset = 0

        except KeyboardInterrupt:
            break
        except Exception as e:
            stdscr.addstr(height - 1, 0, f"Error in writer thread: {e}", curses.color_pair(1))
            stdscr.refresh()
            break

def cleanup(stdscr=None):
    """
    Clean up resources and ensure the terminal is restored to its normal state.

    Args:
        stdscr (curses.window, optional): The curses window object. Defaults to None.
    """
    if stdscr:
        try:
            curses.nocbreak()
            stdscr.keypad(False)
            curses.echo()
            curses.endwin()
        except Exception as e:
            print(f"Error during cleanup: {e}")
    else:
        curses.endwin()
    print("Cleanup completed.")
