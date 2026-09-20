# -*- coding: utf-8 -*-
"""
TermGuard 内置演示数据 —— 游戏本地化场景
故意埋入多种典型错误，用于 Demo 展示检查引擎能力。
每处错误都配有注释说明对应哪类 QA 问题。
"""

SAMPLE_GLOSSARY = [
    {"source": "Cloud Sync", "target": "云同步", "context": "设置-存档同步", "keep_english": False, "note": "产品功能名"},
    {"source": "HP", "target": "生命值", "context": "战斗属性", "keep_english": False, "note": "禁止使用“健康点”"},
    {"source": "Mana", "target": "法力值", "context": "战斗属性", "keep_english": False, "note": ""},
    {"source": "Cooldown", "target": "冷却时间", "context": "技能", "keep_english": False, "note": "避免口语缩写 CD"},
    {"source": "Quest", "target": "任务", "context": "任务系统", "keep_english": False, "note": "统一译“任务”，勿用“委托”"},
    {"source": "Arena", "target": "竞技场", "context": "PvP", "keep_english": False, "note": ""},
    {"source": "GvG", "target": "GvG", "context": "公会战", "keep_english": True, "note": "公会战缩写保留英文"},
    {"source": "Legionnaire's Blade", "target": "Legionnaire's Blade", "context": "首领名称", "keep_english": True, "note": "专有名词保留英文"},
    {"source": "Level", "target": "等级", "context": "角色等级", "keep_english": False, "note": "角色等级语境"},
    {"source": "Level 3", "target": "第 3 章", "context": "关卡/章节", "keep_english": False, "note": "上下文限定词条：章节语境"},
    {"source": "Soulbound", "target": "灵魂绑定", "context": "物品", "keep_english": False, "note": ""},
    {"source": "Inventory", "target": "背包", "context": "物品栏", "keep_english": False, "note": ""},
]

# (id, 源文, 译文)
SAMPLE_ENTRIES = [
    (1,  "Welcome back, Commander! Your base has been upgraded.",
         "欢迎回来，指挥官！你的基地已升级。"),                                        # OK
    (2,  "Synchronizing your save data with Cloud Sync...",
         "正在将存档与云备份同步……"),                                                  # ✗ 术语：Cloud Sync 应为“云同步”（与第3行不一致）
    (3,  "Cloud Sync is now enabled for all your devices.",
         "云同步现已对所有设备开启。"),                                                # OK（对照第2行）
    (4,  "Reach Level 10 to unlock the Arena, {player}!",
         "达到等级 10 即可解锁竞技场！"),                                              # ✗ 占位符 {player} 丢失
    (5,  "Daily Quest completed: The Merchant's Request.",
         "每日任务完成：「商人的请求」。"),                                             # OK（Quest→任务）
    (6,  "Weekly Quest progress has been reset.",
         "每周委托进度已重置。"),                                                      # ✗ 术语：Quest 应为“任务”，与第5行不一致
    (7,  "Use a Mana Potion to restore 50 Mana.",
         "使用法力药剂恢复 5000 点法力值。"),                                          # ✗ 数字：50 → 5000
    (8,  "Press [E] to open your Inventory.",
         "按 E 键打开背包。"),                                                          # ✗ 占位符 [E] 丢失/被改写
    (9,  "Loading game assets, please wait...",
         ""),                                                                           # ✗ 漏译：译文为空
    (10, "Ability cooldown reduced to 15 seconds.",
         "技能 CD 减至 15 秒。"),                                                       # ✗ 术语：Cooldown 应为“冷却时间”（口语缩写）
    (11, "You cannot fast travel while in combat.",
         "战斗中无法快速旅行。"),                                                       # OK
    (12, "The Guild vs Guild (GvG) season begins this Friday.",
         "公会战赛季将于本周五开启。"),                                                 # ✗ 术语：GvG 缩写应保留
    (13, "Defeat the boss Legionnaire's Blade to claim your loot.",
         "击败首领军团之刃，获得你的战利品。"),                                         # ✗ 术语：专有名词 Legionnaire's Blade 应保留英文
    (14, "Guild members earn +10% gold from quests.",
         "公会成员完成任务获得的金币增加 100%。"),                                     # ✗ 数字：10 → 100
    (15, "Save your progress before logging out.",
         "登出前请保存游戏进度。"),                                                     # OK
    (16, "Soulbound items cannot be traded or mailed.",
         "灵魂绑定物品无法交易或邮寄。"),                                               # OK
    (17, "Quest marker: Level 3 - The Ruins of Ashfall.",
         "任务标记：等级 3 灰烬废墟。"),                                                # ✗ 术语(上下文限定)：Level 3 在章节语境应为“第 3 章”
    (18, "A new Arena season starts in 3 days.",
         "新竞技场赛季将在 3 天后开启。"),                                              # OK
    (19, "This item is bound to your account and cannot be shared.",
         "此物品已绑定你的账号，无法共享。"),                                           # OK
    (20, "Error 404: Asset not found. Please verify the resource path.",
         "错误 404：未找到资源，请检查资源路径。"),                                    # OK（数字 404 两侧一致，不应误报）
    (21, "Healing Potion restores 200 HP over 10 seconds.",
         "治疗药水在 10 秒内恢复 200 点生命值。"),                                     # OK
    (22, "Your HP is low! Drink a potion or retreat now.",
         "你的健康点过低！请立即喝药水或撤退。"),                                       # ✗ 术语：HP 应为“生命值”
    (23, "Fast Travel becomes available at Level 5.",
         "等级 5 时解锁快速旅行。"),                                                    # OK（角色等级语境）
    (24, "Collect 5 rare herbs, 3 monster fangs, and return them to the alchemist "
         "to craft the Stormcaller Potion.",
         "收集 5 株稀有药草和 3 颗怪物獠牙，交给炼金术士。"),                          # ✗ 疑似漏译：后半句(制作风暴召唤药剂)缺失
    (25, "This message will self-destruct in 10 seconds.",
         "This message will self-destruct in 10 seconds."),                            # ✗ 未翻译：译文与源文相同
    (26, "Guild disbanded: the leader has been inactive for 90 days.",
         "公会已解散：会长已 90 天未上线。"),                                          # OK
]

def get_sample():
    entries = [{"line": i, "source": s, "target": t} for (i, s, t) in SAMPLE_ENTRIES]
    return {"entries": entries, "glossary": SAMPLE_GLOSSARY}
