import curses
import queue

def display_intro(stdscr: curses.window) -> None:
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
        while len(paragraph) > width or (len(lines) == 0 and len(paragraph) > width - start_pos):
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

def find_matching_message(messages, source, label, final):
    """
    Find the index of the matching message in the list.

    Args:
        messages (list): List of message dictionaries.
        source (str): The source of the message to find.
        label (str): The label of the message to find.
        final (bool): Whether to find a final or non-final message.

    Returns:
        int: The index of the matching message, or -1 if not found.
    """
    for i, msg in enumerate(messages):
        if msg["source"] == source and (msg["label"] == label or label == None) and msg["final"] == final:
            return i
    return -1

def writer_thread(stdscr: curses.window, message_queue: queue.Queue) -> None:
    """
    Continuously retrieves messages from the queue and displays them in the terminal window.

    Args:
        stdscr (curses.window): The curses window object.
        message_queue (queue.Queue): Queue from which messages are retrieved.
    """
    stdscr.scrollok(True)
    message_positions = {
        "left": [],
        "right": []
    }
    scroll_offset = 0

    while True:
        try:
            source, label, text, side, final = message_queue.get()

            # Find the message to update or append a new one
            found_message = False
            match_index = find_matching_message(message_positions[side], source, label, False)
            if match_index != -1:
                wrapped_lines = wrap_text(text, stdscr.getmaxyx()[1] // 2 - 2)

                # Update the existing non-final message
                message_positions[side][match_index]["text"] = text
                message_positions[side][match_index]["final"] = final
                message_positions[side][match_index]["lines"] = len(wrapped_lines) + 2
                y_pos_start = message_positions[side][match_index]["y_pos_start"]
                message_positions[side][match_index]["y_pos_end"] = y_pos_start + len(wrapped_lines)
                found_message = True

            if not found_message:
                # Calculate y_pos_start based on the maximum y_pos_end + 2 for the current side's messages
                y_pos_start = max(
                    (msg["y_pos_end"] for msg in message_positions[side]),
                    default=-1
                ) + 1

                # Calculate y_pos_start based on the other side's last matching message if it's greater
                opposite_side = "left" if side == "right" else "right"
                matching_index_opposite = find_matching_message(message_positions[opposite_side], source, None, True)
                y_pos_start = max(
                    y_pos_start,
                    max(
                        (msg["y_pos_start"] for msg in message_positions[opposite_side] if msg["source"] == source),
                        default=0
                    )
                )
                if len(message_positions[opposite_side]) > 1 and matching_index_opposite != -1:
                    y_pos_start = max(
                        y_pos_start,
                        message_positions[opposite_side][matching_index_opposite]["y_pos_end"] + 1
                    )

                wrapped_lines = wrap_text(text, stdscr.getmaxyx()[1] // 2 - 2)

                message_positions[side].append({
                    "source": source,
                    "label": label,
                    "text": text,
                    "final": final,
                    "lines": len(wrapped_lines) + 2,
                    "y_pos_start": y_pos_start,
                    "y_pos_end": y_pos_start + len(wrapped_lines)
                })

            # Recalculate total lines after updating or adding a new message
            total_lines = max(
                max((msg["y_pos_end"] for msg in message_positions["left"]), default=0),
                max((msg["y_pos_end"] for msg in message_positions["right"]), default=0)
            )

            # Handle scrolling if needed
            max_y, _ = stdscr.getmaxyx()
            max_y -= 1
            if total_lines > max_y:
                scroll_offset = total_lines - max_y

            # Clear the screen and recalculate all positions for both sides
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            mid_x = width // 2

            for side in ["left", "right"]:
                for msg in message_positions[side]:
                    y_pos = msg["y_pos_start"] - scroll_offset
                    x_pos = 0 if side == "left" else mid_x + 1
                    wrapped_lines = wrap_text(msg["text"], mid_x - 2 if side == "left" else width - mid_x - 2)
                    if y_pos >= 0:
                        stdscr.addstr(y_pos, x_pos, f"{msg['source']} ({msg['label']}):", curses.A_BOLD)
                    for i, line in enumerate(wrapped_lines):
                        if y_pos + i + 1 >= 0:
                            stdscr.addstr(y_pos + i + 1, x_pos, line)
                    msg["y_pos_start"] = y_pos
                    msg["y_pos_end"] = y_pos + msg["lines"] - 1

            # Remove messages that are entirely off-screen
            message_positions["left"] = [msg for msg in message_positions["left"] if msg["y_pos_end"] >= 0]
            message_positions["right"] = [msg for msg in message_positions["right"] if msg["y_pos_end"] >= 0]
            scroll_offset = 0

            stdscr.refresh()

        except KeyboardInterrupt:
            break
        except Exception as e:
            stdscr.addstr(height - 1, 0, f"Error in writer thread: {e}", curses.color_pair(1))
            stdscr.refresh()
            break

def cleanup(stdscr: curses.window = None) -> None:
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
