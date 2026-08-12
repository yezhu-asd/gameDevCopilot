extends Node2D

# 塔防敌人 —— 骨架。沿路径点移动，到终点发信号。

signal reached_end(enemy)

var path: Array[Vector2] = []
var path_index := 0
var speed := 120.0
var hp := 20.0

func _physics_process(delta: float) -> void:
	if path_index >= path.size():
		return
	var target := path[path_index]
	global_position = global_position.move_toward(target, speed * delta)
	if global_position.distance_to(target) < 4.0:
		path_index += 1
		if path_index >= path.size():
			reached_end.emit(self)
			queue_free()
