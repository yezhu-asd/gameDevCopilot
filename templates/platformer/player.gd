extends CharacterBody2D

# 平台跳跃玩家 —— 骨架。玩法细节（速度、跳跃力、收集、敌人）由 LLM 在骨架上填充。

const SPEED := 300.0
const JUMP_VELOCITY := -600.0
const GRAVITY := 1200.0

func _physics_process(delta: float) -> void:
	velocity.y += GRAVITY * delta
	var dir := Input.get_axis("ui_left", "ui_right")
	if dir != 0.0:
		velocity.x = dir * SPEED
	else:
		velocity.x = move_toward(velocity.x, 0.0, SPEED)
	if Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = JUMP_VELOCITY
	move_and_slide()
