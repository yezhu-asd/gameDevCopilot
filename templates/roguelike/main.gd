extends Node2D

# Roguelike 主场景 —— 骨架。网格棋盘 + 玩家移动可用。怪物/宝箱/战斗/GameOver 由 LLM 填充。

const GRID_W := 8
const GRID_H := 6
const CELL := 64.0

var occupied: Dictionary = {}  # Vector2i -> true

@onready var player: CharacterBody2D = $Player

func _ready() -> void:
	_generate_map()

func _generate_map() -> void:
	# 简单棋盘：四周为墙，内部为空。可扩展为随机生成。
	for x in range(GRID_W):
		occupied[Vector2i(x, 0)] = true
		occupied[Vector2i(x, GRID_H - 1)] = true
	for y in range(GRID_H):
		occupied[Vector2i(0, y)] = true
		occupied[Vector2i(GRID_W - 1, y)] = true

func is_walkable(pos: Vector2i) -> bool:
	return pos.x >= 1 and pos.x < GRID_W - 1 and pos.y >= 1 and pos.y < GRID_H - 1 and not occupied.has(pos)
