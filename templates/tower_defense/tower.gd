extends Area2D

# 塔防防御塔 —— 骨架。射程内敌人攻击。射程/伤害/攻速可配置。

const RANGE := 150.0
const DAMAGE := 10.0
const FIRE_INTERVAL := 0.8

var fire_timer := 0.0

func _process(delta: float) -> void:
	fire_timer -= delta
	if fire_timer > 0.0:
		return
	var target: Node2D = _find_enemy_in_range()
	if target == null:
		return
	if target.has_method("take_damage"):
		target.take_damage(DAMAGE)
	else:
		target.hp -= DAMAGE
		if target.hp <= 0.0:
			target.queue_free()
	fire_timer = FIRE_INTERVAL

func _find_enemy_in_range() -> Node2D:
	var enemies := get_tree().get_nodes_in_group("enemies")
	var best: Node2D = null
	var best_dist := RANGE
	for e in enemies:
		if not is_instance_valid(e):
			continue
		var d: float = global_position.distance_to(e.global_position)
		if d <= best_dist:
			best_dist = d
			best = e
	return best
