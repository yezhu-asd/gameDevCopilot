extends Node2D

# 塔防主场景 —— 骨架。敌人沿路径刷出、点击放塔、生命/金币。可在此基础上加波次、升级。

const TOWER_COST := 50
const ENEMY_HP := 30.0
const ENEMY_SPEED := 120.0
const SPAWN_INTERVAL := 2.0

const PATH: Array[Vector2] = [Vector2(-50, 300), Vector2(400, 300), Vector2(400, 150), Vector2(850, 150)]

var gold := 100
var lives := 10
var game_over := false
var spawn_timer := 0.0

@onready var gold_label: Label = $UI/GoldLabel
@onready var lives_label: Label = $UI/LivesLabel
@onready var message_label: Label = $UI/MessageLabel

const TowerScene = preload("res://tower.tscn")
const EnemyScene = preload("res://enemy.tscn")

func _ready() -> void:
	_update_ui()

func _process(delta: float) -> void:
	if game_over:
		return
	spawn_timer += delta
	if spawn_timer >= SPAWN_INTERVAL:
		spawn_timer = 0.0
		_spawn_enemy()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_try_place_tower(get_global_mouse_position())

func _spawn_enemy() -> void:
	var e = EnemyScene.instantiate()
	e.path = PATH
	e.hp = ENEMY_HP
	e.speed = ENEMY_SPEED
	e.reached_end.connect(_on_enemy_reached_end)
	add_child(e)

func _try_place_tower(pos: Vector2) -> void:
	if gold < TOWER_COST:
		message_label.text = "金币不足!"
		return
	gold -= TOWER_COST
	var t = TowerScene.instantiate()
	t.position = pos
	add_child(t)
	_update_ui()

func _on_enemy_reached_end(_enemy) -> void:
	lives -= 1
	_update_ui()
	if lives <= 0:
		game_over = true
		message_label.text = "游戏结束!"

func _update_ui() -> void:
	gold_label.text = "金币: %d" % gold
	lives_label.text = "生命: %d" % lives
