# 页面规格约定

每页在进入生图前都必须先落成结构化规格，至少包含：

- `page_index`
- `page_title`
- `title_text`
- `display_title_mode`
- `display_title`
- `source_title_full`
- `subtitle_notes`
- `cue_phrases`
- `flow_labels`
- `support_labels`
- `page_body`
- `page_type`
- `page_background_mode`
- `background_color`
- `line_color`
- `scene_priority`
- `scene_concept`
- `scene_layout_type`
- `title_layout_mode`
- `title_alignment`
- `title_anchor_zone`
- `title_flow_direction`
- `supporting_micro_visuals`
- `role_scene_relationship`
- `role_in_scene_mode`
- `role_in_scene_guidance`
- `reserved_zone`
- `reserved_zone_rules`
- `pagination_mode`
- `section_kind`
- `step_label`
- `step_index`
- `step_page_index`
- `step_page_total`
- `is_continued`
- `role_action`
- `role_expression`
- `role_expression_tags`
- `forbid_visible_page_number`
- `role_identity_lock`
- `role_scale`
- `role_position`
- `role_framing`
- `role_composition_mode`
- `camera_energy`
- `role_pose_hint`
- `role_variation_guard`
- `role_variation_reason`
- `icon_set`
- `layout_constraints`
- `visual_action_cues`
- `visual_scene_cues`
- `role_action_tags`
- `text_density_mode`

## 分页模式

- `pagination_mode = explicit`
  - 输入文案中存在 `---`
  - 绝不自动重分
- `pagination_mode = auto`
  - 输入文案中没有 `---`
  - 先识别导语、步骤块、尾声，再自动分页

## 自动分页约束

- 导语可以按语义切成 1 页或多页
- `第一点 / 第二点 / 第三点` 是硬边界
- 不同步骤绝不混页
- 每个步骤至少一页
- 长步骤允许拆成续页
- 续页标题自动总结

## 固定版式

- 16:9
- 标题大字号
- 额外文字以原文提炼提示词为主，允许少量受控补字
- 手绘视觉笔记风
- 左下角 13cm × 13cm 纯底色禁绘区域

## 配图 / 配字双轨

- 配图逻辑：
  - 从原文意思里提炼动作、行为、场景语义
  - 对应字段：`visual_action_cues`、`visual_scene_cues`、`role_action_tags`
  - 这些字段可以服务于“打篮球、打游戏、写作、用电脑、谈销售”等动作化表达
- 配字逻辑：
  - 以原文已有文字提炼标题词、关键词、流程词为主
  - 对应字段：`title_text`、`display_title`、`cue_phrases`、`flow_labels`
  - 允许通过 `support_labels`、`subtitle_notes` 少量补充结构说明
  - 这些字段才允许变成页面上真正可见的文字
- 配图字段默认不能自动变成页面新增文字；只有被规格层明确下沉到 `support_labels` 时，才能少量显示

## 场景优先规则

- 主标题先决定整页主场景
- 人物进入主场景出演，不先摆主持人模板
- 所有页面都必须以自己的主题为核心，人物只是配合主题，不是默认世界中心
- 人物不是默认视觉中心，场景、标题、结构和留白一起决定主视觉重心
- 小词和小图只做局部解释，不抢整页主视觉
- `cue_phrases` 仍以该页原文抽取、压缩、重组为主
- `support_labels` 只允许补极短结构说明词，不允许长句、批注墙或满屏堆字
- 长标题页允许压缩主标题：
  - `display_title_mode = exact`
    - 主标题直接显示原句
  - `display_title_mode = compressed`
    - 主标题显示压缩后的 `display_title`
    - 原句剩余语义拆进 `subtitle_notes`
- 标题本身也是画面的一部分，不是固定条幅模板
- 每页要像一张独立海报页，标题位置跟场景走

首版主场景：

- `pit-map`
- `production-line`
- `path-flow`
- `contrast-split`
- `blocked-structure`
- `summary-stage`
- `cover-hero`

## 标题布局规则

- 标题布局默认随场景自动变化
- 标题可以居中、偏左、偏右、横跨顶部，或融入结构内部
- 但每页仍然只有一个主标题
- 主标题必须是该页最强文字锚点

首版标题布局模式：

- `center-hero`
- `top-span`
- `left-anchor`
- `right-anchor`
- `inline-scene`

## 角色构图规则

- 第 1 页仍然是正文第 1 页，不单独改名为封面页；如果主题需要，可以做出更强的主视觉感
- 普通内容页即使是第 1 页，也不要默认把人物放中间
- 后续页面不要一直把人物放中间
- 人物必须进入主场景内部，不能作为画外独立主持人贴在一侧
- 人物必须和当前页至少一个主结构发生直接动作关系，例如触碰、操作、跨越、连接、被限制
- 不允许“右边一个独立人物 + 左边一堆内容”这种默认拼贴构图
- 角色大小必须变化：
  - `small-accent`
  - `medium-support`
  - `large-focus`
- 角色景别必须变化：
  - `full-body`
  - `three-quarter`
  - `half-body`
- 角色动作要结合标题场景，不要每页都是普通主持姿态
- 同一选题内，相邻页和近邻页不要复用近似动作语义、近似表情语义，或“相同景别 + 相同站位 + 相同演法”组合
- 当主题相近时，优先通过动作簇、表情簇、姿态提示、嵌入方式拉开差异
- 页面上禁止出现任何页码、页序、角标编号、`x/y` 计数
- 人物允许更 Q 版，但只能改变夸张程度，不能改变白西装、黑色内搭、背头侧分、黑框眼镜、既定脸型和九宫格定标板锁定的身份识别点
- 严禁出现卫衣、套头衫、便装外套、卷发、前梳发型或陌生脸
- 结构页以图示为主时，人物应主动缩小为点缀或支撑
- 情绪页以人物演法为主时，人物可以明显放大

首版人物入场模式：

- `embedded-actor`
- `structure-interactor`
- `scene-operator`
- `contrast-bridge`

默认映射：

- `对比页`：优先 `contrast-bridge`
- `流程页`：优先 `scene-operator`
- `结构页 / 误区页`：优先 `structure-interactor`
- `总结页`：优先 `embedded-actor`

## 左下角留白区规则

- 每页左下角都预留 13cm × 13cm 区域
- 该区域只保留页面原本纯底色，并且看起来只是背景自然延续
- 该区域是硬性禁区，不允许人物、标题、图标、箭头、装饰线、坑位边缘、脚印或残留阴影进入
- 该区域不能画成框、格子、占位提示或任何显式边界
- 区域内不能出现：
  - 文字
  - 图标
  - 人物
  - 线条
  - 箭头
  - 脚印
  - 坑位边缘
  - 装饰元素

## 固定配色

- 单数页背景：`#fcb537`
- 双数页背景：`#122142`
- 单数页线条：黑色
- 双数页线条：白色

---
• 带你用AI，把你的能力变成你的生意
• 有使用问题，或加入我的会员答疑群！
• 姜来已来2046，联系微信： lact175
---
