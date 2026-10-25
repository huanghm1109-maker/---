# 离线词典

`ecdict.sqlite3` 由 [ECDICT](https://github.com/skywind3000/ECDICT) 官方
`ecdict.csv` 转换而来，共 770,611 条词条。

- 数据版本：ECDICT 1.0.28 / master CSV
- 许可证：MIT，完整文本见 `ECDICT-LICENSE.txt`
- 查询字段：单词、音标、中文释义、英文释义、词汇标签（tag）

程序只以只读模式打开该数据库，翻译时不会访问网络。

ECDICT 原始数据中的 `tag` 字段使用空格分隔，例如
`gk cet4 cet6 ky toefl`。数据库迁移脚本和备份说明见项目根目录的
`migrate_cet_tags.py`；迁移后可用空格边界匹配 CET4/CET6，避免把
`notcet4` 之类的文字误判为四六级标签。
