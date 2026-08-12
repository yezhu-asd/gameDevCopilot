extends Node2D

# 平台跳跃主场景 —— 骨架。玩家移动/跳跃/碰撞已可用，可在此基础上加金币、敌人、关卡。

@onready var player: CharacterBody2D = $Player
@onready var coin_counter: Label = $UI/CoinCounter

var coins := 0

func _ready() -> void:
	_update_coin_counter()

func _update_coin_counter() -> void:
	coin_counter.text = "金币: %d" % coins

func _on_coin_collected() -> void:
	coins += 1
	_update_coin_counter()
