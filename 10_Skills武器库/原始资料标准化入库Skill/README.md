# 原始资料标准化入库Skill

这是小息处理书籍原始资料的正式标准化入口。

主要职责：

- 识别当前原始知识库中的待标准化书源；
- 把可读资料转换为正式 `《书名》.md`；
- 统一文件名、分类目录和原始资料输入清单；
- 将标准化结果交给小审执行原始资料入库审核。

工作区根路径统一使用环境变量 `AI_TRAFFIC_FACTORY_ROOT`。默认执行为预演，只有显式提供 `--apply` 时才写入文件。

```text
python scripts/normalize_raw_materials.py --root <workspace-root>
python scripts/normalize_raw_materials.py --root <workspace-root> --category <分类目录> --apply
```

本 Skill 不负责筛书、拆书或生成文案。

---

• 带你用AI，把你的能力变成你的生意
• 有使用问题，或加入我的会员答疑群！
• 姜来已来2046，联系微信： lact175

---
