import math
import argparse
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'

pixels_painted = 0

XP_PER_LEVEL =  100
WAIT_PER_PIXEL = 30 # seconds
MAX_PIXEL_INCREASE_PER_LEVEL = 2
SECONDS = 60 # per minute
MINUTES = 60 # per hour
xp = 100
level = 1
sessions = 0
leveled_up = False
max_pixel_limit = 62
wait_total = 0 # seconds till next block
droplets_total = 0
droplets_goal = 20000
goal_completion_time = 0 # seconds till goal completion (only the wait time--not the time spent painting)

def paint_blocks(pixels: int):
  global xp, droplets_total, pixels_painted, max_pixel_limit, level, wait_total
  wait_total = pixels * WAIT_PER_PIXEL
  xp += pixels
  droplets_total += pixels
  pixels_painted += pixels
  max_pixel_limit += MAX_PIXEL_INCREASE_PER_LEVEL
  if ((xp // XP_PER_LEVEL) > level):
    droplets_total += 500
  level = xp // XP_PER_LEVEL

def calculate_completion(stop_on: str = "droplets"):
  global droplets_total, goal_completion_time, sessions, wait_total, max_pixel_limit
  while True:
    if stop_on == "droplets" and droplets_total >= droplets_goal:
      break
    if stop_on == "level" and level >= level_goal:
      break
    paint_blocks(max_pixel_limit)
    canvas_size = int(math.sqrt(max_pixel_limit))
    print(f"Wait: {YELLOW}{int(wait_total/SECONDS)} min{RESET} — {CYAN}{max_pixel_limit} pixels{RESET} — Canvas: {GREEN}{canvas_size}×{canvas_size}{RESET} — Level: {RED}{level}{RESET}")
    goal_completion_time += wait_total
    sessions += 1
  hours = int((goal_completion_time/SECONDS)/MINUTES)
  minutes = int((goal_completion_time/SECONDS) % MINUTES)
  grand_canvas_size = int(math.sqrt(pixels_painted))
  print(f"Wait time total till goal of {droplets_goal:,} droplets: {YELLOW}{hours} Hours{RESET}, {YELLOW}{minutes} Minutes{RESET}, and {sessions} sessions total")
  print(f"Total Pixels Painted: {CYAN}{pixels_painted:,}{RESET} - Canvas: {GREEN}{grand_canvas_size}×{grand_canvas_size}{RESET}")


def parse_canvas_arg(canvas_arg: str) -> int:
  if "x" in canvas_arg.lower():
    parts = canvas_arg.lower().split("x")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
      raise ValueError("--canvas must be like 30x30")
    side_a = int(parts[0])
    side_b = int(parts[1])
    if side_a != side_b:
      raise ValueError("--canvas must be square like 30x30 (sides equal)")
    return side_a * side_b
  # Allow single side, treat as NxN
  if canvas_arg.isdigit():
    side = int(canvas_arg)
    return side * side
  raise ValueError("Invalid --canvas value")


def side_from_pixels(pixels: int) -> int:
  root = int(math.isqrt(pixels))
  if root * root != pixels:
    raise ValueError("max-pixels must be a perfect square to derive canvas")
  return root


def reset_state():
  global xp, level, sessions, leveled_up, wait_total, droplets_total, goal_completion_time, pixels_painted
  xp = 100
  level = 1
  sessions = 0
  leveled_up = False
  wait_total = 0
  droplets_total = 0
  goal_completion_time = 0
  pixels_painted = 0


def main():
  global max_pixel_limit, droplets_goal, level_goal, xp, level, goal_completion_time, sessions, wait_total
  parser = argparse.ArgumentParser(description="WPlace simulator with solver for unknowns")
  parser.add_argument("--max-pixels", dest="max_pixels", help="Pixels per session (square). Use 'x' to solve.")
  parser.add_argument("--canvas", dest="canvas", help="Canvas as NxN (e.g., 30x30). Use 'x' to solve.")
  parser.add_argument("--droplets", dest="droplets", help="Target droplets. Use 'x' to solve.")
  parser.add_argument("--levels", dest="levels", help="Target level. Use 'x' to solve.")
  parser.add_argument("--current-level", dest="current_level", help="Your current level (starting point)")
  parser.add_argument("--target-max-pixels", dest="target_max_pixels", help="Desired future max-pixels; compute level when this is reached")
  args = parser.parse_args()

  if not any([args.max_pixels, args.canvas, args.droplets, args.levels]):
    # No args: run default behavior
    calculate_completion(stop_on="droplets")
    return

  # Determine unknowns
  provided = {
    "max_pixels": args.max_pixels,
    "canvas": args.canvas,
    "droplets": args.droplets,
    "levels": args.levels,
  }
  unknown_keys = [k for k, v in provided.items() if isinstance(v, str) and v.lower() == "x"]
  if len(unknown_keys) > 1:
    raise SystemExit("Only one parameter can be 'x' at a time.")

  # Resolve max_pixels/canvas relationship first (no simulation needed)
  resolved_max_pixels = None
  if args.max_pixels and args.max_pixels.lower() != "x":
    if not args.max_pixels.isdigit():
      raise SystemExit("--max-pixels must be an integer or 'x'")
    resolved_max_pixels = int(args.max_pixels)
  if args.canvas and args.canvas.lower() != "x":
    canvas_pixels = parse_canvas_arg(args.canvas)
    if resolved_max_pixels is not None and resolved_max_pixels != canvas_pixels:
      raise SystemExit("--max-pixels and --canvas disagree")
    resolved_max_pixels = canvas_pixels
  if args.max_pixels and args.max_pixels.lower() == "x":
    if args.canvas and args.canvas.lower() != "x":
      resolved_max_pixels = parse_canvas_arg(args.canvas)
      print(f"Solved max-pixels: {CYAN}{resolved_max_pixels}{RESET}")
    else:
      raise SystemExit("To solve --max-pixels, provide concrete --canvas")
  if args.canvas and args.canvas.lower() == "x":
    if resolved_max_pixels is None:
      raise SystemExit("To solve --canvas, provide concrete --max-pixels")
    side = side_from_pixels(resolved_max_pixels)
    print(f"Solved canvas: {GREEN}{side}×{side}{RESET}")

  if resolved_max_pixels is not None:
    max_pixel_limit = resolved_max_pixels

  # Resolve droplets/levels via simulation
  resolved_droplets = None
  resolved_level = None
  level_goal = None

  if args.droplets and args.droplets.lower() != "x":
    if not args.droplets.isdigit():
      raise SystemExit("--droplets must be an integer or 'x'")
    droplets_goal = int(args.droplets)
  if args.levels and args.levels.lower() != "x":
    if not args.levels.isdigit():
      raise SystemExit("--levels must be an integer or 'x'")
    level_goal = int(args.levels)

  # Decide stop condition
  stop_on = "droplets"
  if args.levels and args.levels.lower() != "x" and (not args.droplets or args.droplets.lower() == "x"):
    stop_on = "level"

  # Special mode: given current level and current max-pixels, find level when target max-pixels is achievable
  if args.target_max_pixels:
    if not args.target_max_pixels.isdigit():
      raise SystemExit("--target-max-pixels must be an integer")
    target_max = int(args.target_max_pixels)

    # Resolve starting max-pixels
    if resolved_max_pixels is None:
      raise SystemExit("Provide your current --max-pixels or --canvas as the starting point")

    # Resolve starting level
    starting_level = 1
    if args.current_level:
      if not args.current_level.isdigit():
        raise SystemExit("--current-level must be an integer")
      starting_level = int(args.current_level)

    # Simulate progression until max-pixel limit reaches target
    reset_state()
    # Set starting state
    xp = starting_level * XP_PER_LEVEL
    # level will be recomputed via paint_blocks, but set initial
    level = starting_level
    max_pixel_limit = resolved_max_pixels
    # Do not print per-iteration logs in this mode
    while max_pixel_limit < target_max:
      paint_blocks(max_pixel_limit)
      goal_completion_time += wait_total
      sessions += 1

    print(f"Starting Level: {RED}{starting_level}{RESET} — Starting Max Pixels: {CYAN}{resolved_max_pixels}{RESET}")
    print(f"Target Max Pixels: {CYAN}{target_max}{RESET} reached after {sessions} sessions")
    print(f"Level at target: {RED}{level}{RESET}")
    return

  if (args.droplets and args.droplets.lower() == "x") or (args.levels and args.levels.lower() == "x") or stop_on == "level" or droplets_goal:
    reset_state()
    calculate_completion(stop_on=stop_on)
    resolved_droplets = droplets_total
    resolved_level = level

  # Report solved unknowns
  if args.droplets and args.droplets.lower() == "x":
    print(f"Solved droplets: {CYAN}{resolved_droplets:,}{RESET}")
  if args.levels and args.levels.lower() == "x":
    print(f"Solved level: {RED}{resolved_level}{RESET}")


if __name__ == "__main__":
  main()

  