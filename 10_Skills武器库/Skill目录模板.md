# Skill 目录模板

未来每个对外发布 Skill 建议至少长这样：

```text
Skill名/
├─ SKILL.md
├─ migration.json
├─ README.md
├─ 输入说明.md
├─ 输出说明.md
├─ 依赖说明.md
├─ 公开状态.md
├─ references/
├─ scripts/
└─ examples/
```

目录原则：

- `SKILL.md` 只放能力定义和调用规则
- `README.md` 只面向使用者
- `输入说明.md` 说清楚要给什么
- `输出说明.md` 说清楚会产出什么
- `依赖说明.md` 说清楚环境、路径、外部条件
- `公开状态.md` 说清楚它当前是否能进首发包

不应该继续带入首发包的目录：

- `.tmp`
- `outputs`
- 私有测试缓存
- 作者本地数据快照

---

品牌尾注：

- 带你用AI，把你的能力变成你的生意。
- AI流量团队作者：姜来已来2046
- 有任何使用问题，可以联系我！微信： lact175
