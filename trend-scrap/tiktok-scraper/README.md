# TikTok Scraper

使用 Apify API 爬取 TikTok 数据的工具。

## 功能

- 🔍 通过关键词搜索 TikTok 视频
- 🧹 自动清洗数据，提取关键字段
- � Filter 根据播放量、点赞数等条件筛选数据
- 💾 将数据保存为 JSON 格式到本地
- 📊 提供数据统计分析功能

## 安装

```bash
cd tiktok-scraper
npm install
```

## 配置

1. 复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的 API Token：

```env
APIFY_TOKEN=你的APIFY_TOKEN
```

3. (可选) 编辑 `config/config.json` 自定义筛选条件：

```json
{
  "defaultQueries": ["chatGPT"],
  "filters": {
    "minPlayCount": 100000,
    "minDiggCount": 100
  }
}
```

## 使用方式

### 1. 命令行运行

```bash
npm start
# 或
node src/scraper.js
```

### 2. 作为模块使用

```javascript
const { TikTokScraper } = require('./src/scraper');

async function main() {
  const scraper = new TikTokScraper({
    apifyToken: 'YOUR_API_TOKEN'
  });

  const result = await scraper.scrape(['chatGPT'], {
    resultsPerPage: 20,
    shouldDownloadVideos: false
  });

  console.log(result);
}

main();
```

## 输出字段

清洗后的 JSON 包含以下字段：

| 字段 | 说明 |
|------|------|
| id | 视频ID |
| text | 视频文案 |
| textLanguage | 文案语言 |
| videoMeta.duration | 视频时长(秒) |
| videoMeta.downloadAddr | 视频下载链接 |
| videoMeta.coverUrl | 封面图链接 |
| diggCount | 点赞数 |
| shareCount | 分享数 |
| playCount | 播放量 |
| authorMeta.nickName | 作者昵称 |
| authorMeta.fans | 粉丝数 |
| hashtags | 话题标签 |
| webVideoUrl | 视频链接 |

## 数据存储

原始数据和筛选后的数据分别保存在 `data/` 目录下：

- `raw_*_timestamp.json` - 原始数据
- `filtered_*_timestamp.json` - 筛选后数据

## API 参考

### Apify TikTok Scraper

- Actor ID: `GdWCkxBtKWOsKjdch`
- 官方文档: https://apify.com/clockworks/tiktok-scraper
