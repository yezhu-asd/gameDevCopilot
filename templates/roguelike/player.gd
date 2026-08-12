extends CharacterBody2D

# Roguelike 网格移动玩家 —— 骨架。按键瞬移一格，碰撞已配置。

const CELL_SIZE := 64.0
const SPEED := 0.0  # 网格移动不走物理，见 _physics_process

var grid_pos := Vector2i(2, 3)

func _physics_process(_delta: float) -> void:
	var dir := Vector2i.ZERO
	if Input.is_action_just_pressed("ui_left"):
		dir = Vector2i(-1, 0)
	elif Input.is_action_just_pressed("ui_right"):
		dir = Vector2i(1, 0)
	elif Input.is_action_just_pressed("ui_up"):
		dir = Vector2i(0, -1)
	elif Input.is_action_just_pressed("ui_down"):
		dir = Vector2i(0, 1)
	if dir != Vector2i.ZERO:
		_try_move(dir)

func _try_move(dir: Vector2i) -> void:
	var target := grid_pos + dir
	# 由主场景决定是否可通行（如墙/边界）。
	var main := get_parent() as Node2D
	if main.has_method("is_walkable"):
		if not main.is_walkable(target):
			return
	grid_pos = target
	position = Vector2(grid_pos) * Vector2(CELL_SIZE, CELL_SIZE)
