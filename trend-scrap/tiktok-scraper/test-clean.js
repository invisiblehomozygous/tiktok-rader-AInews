/**
 * TikTok 数据清洗测试脚本
 * 使用示例数据测试清洗和筛选功能
 */

const fs = require('fs');
const path = require('path');
const { TikTokScraper } = require('./src/scraper');

// 读取示例数据（从用户的 RTF 文件中提取的 JSON）
const sampleDataPath = '/Users/greaterbay/Documents/apiresult_fortest/test_result.rtf';

// 手动构建测试数据（基于用户提供的示例）
const testData = [
  {
    "id": "7612142088364494087",
    "text": "Helooo @ChatGPT?!! #tipskerjavina #RamadanDiTikTok",
    "textLanguage": "en",
    "createTime": 1772366400,
    "createTimeISO": "2026-03-01T12:00:00.000Z",
    "locationCreated": "ID",
    "isAd": false,
    "authorMeta": {
      "id": "6817822124175967234",
      "name": "vmuliana",
      "profileUrl": "https://www.tiktok.com/@vmuliana",
      "nickName": "Vina Muliana",
      "verified": false,
      "fans": 10064618,
      "following": 162
    },
    "musicMeta": {
      "musicName": "original sound - rnb_source",
      "musicAuthor": "R&B SOURCE",
      "playUrl": "https://sf16-ies-music-sg.tiktokcdn.com/obj/tiktok-obj/7341176748019895042.mp3"
    },
    "webVideoUrl": "https://www.tiktok.com/@vmuliana/video/7612142088364494087",
    "videoMeta": {
      "height": 1024,
      "width": 576,
      "duration": 26.981,
      "coverUrl": "https://p16-sign-sg.tiktokcdn.com/tos-alisg-p-0037/o0ujjTANRCfIIwOBDAIAeOXebl0AZLEGA0oEN4~tplv-tiktokx-cropcenter:500:800.jpeg",
      "definition": "540p",
      "format": "mp4",
      "downloadAddr": "https://api.apify.com/v2/key-value-stores/b7guYtrm7Milwa4BJ/records/video-vmuliana-20260301120000-7612142088364494087.mp4"
    },
    "diggCount": 81106,
    "shareCount": 14394,
    "playCount": 771881,
    "collectCount": 55119,
    "commentCount": 193,
    "hashtags": [
      { "id": "1708066076166153", "name": "tipskerjavina" },
      { "id": "7078598966719283227", "name": "ramadanditiktok" }
    ],
    "mentions": ["@ChatGPT"],
    "searchQuery": "chatGPT"
  },
  {
    "id": "7612306353654107413",
    "text": "C'f3digos para ser m'3s eficiente con ChatGPT. #30X",
    "textLanguage": "es",
    "createTime": 1772378195,
    "createTimeISO": "2026-03-01T15:16:35.000Z",
    "locationCreated": "CO",
    "isAd": false,
    "authorMeta": {
      "id": "7561555612418229268",
      "name": "andres_bilbao0",
      "profileUrl": "https://www.tiktok.com/@andres_bilbao0",
      "nickName": "Andrés Bilbao",
      "verified": false,
      "fans": 145721,
      "following": 4
    },
    "musicMeta": {
      "musicName": "original sound - andres_bilbao0",
      "musicAuthor": "Andrés Bilbao",
      "playUrl": "https://sf16-ies-music-sg.tiktokcdn.com/obj/tiktok-obj/7612306413864094480.mp3"
    },
    "webVideoUrl": "https://www.tiktok.com/@andres_bilbao0/video/7612306353654107413",
    "videoMeta": {
      "height": 1024,
      "width": 576,
      "duration": 49.025,
      "coverUrl": "https://p16-sign-sg.tiktokcdn.com/tos-alisg-p-0037/oUESPtQgUkAFqEFWGURpzpfDwgDRBBeQCEFpXk~tplv-tiktokx-cropcenter:500:800.jpeg",
      "definition": "540p",
      "format": "mp4",
      "downloadAddr": "https://api.apify.com/v2/key-value-stores/b7guYtrm7Milwa4BJ/records/video-andres_bil-20260301151635-7612306353654107413.mp4"
    },
    "diggCount": 42532,
    "shareCount": 13433,
    "playCount": 450144,
    "collectCount": 43463,
    "commentCount": 116,
    "hashtags": [
      { "id": "8371617", "name": "30x" }
    ],
    "mentions": [],
    "searchQuery": "chatGPT"
  },
  {
    "id": "7612510029790350622",
    "text": "Chat gpt is out FOR GOOD #ai #college #students #studytok #hacks",
    "textLanguage": "en",
    "createTime": 1772425633,
    "createTimeISO": "2026-03-02T04:27:13.000Z",
    "locationCreated": "US",
    "isAd": false,
    "authorMeta": {
      "id": "6742696508892857350",
      "name": "jewels.with.julie",
      "profileUrl": "https://www.tiktok.com/@jewels.with.julie",
      "nickName": "jewels.with.julie",
      "verified": false,
      "fans": 1794,
      "following": 311
    },
    "musicMeta": {
      "musicName": "original sound - jewels.with.julie",
      "musicAuthor": "jewels.with.julie",
      "playUrl": "https://sf16.tiktokcdn-us.com/obj/ies-music-tx2/7612515279058291487.mp3"
    },
    "webVideoUrl": "https://www.tiktok.com/@jewels.with.julie/video/7612510029790350622",
    "videoMeta": {
      "height": 1280,
      "width": 720,
      "duration": 61.967,
      "coverUrl": "https://p16-pu-sign-useast8.tiktokcdn-us.com/tos-useast8-p-0068-tx2/oovhYiRIBRAlipHgRGEa6aAEp0DaIZOVmBjUH~tplv-tiktokx-cropcenter:500:800.jpeg",
      "definition": "720p",
      "format": "mp4",
      "downloadAddr": "https://api.apify.com/v2/key-value-stores/b7guYtrm7Milwa4BJ/records/video-jewelswith-20260302042713-7612510029790350622.mp4"
    },
    "diggCount": 22,
    "shareCount": 1,
    "playCount": 417,
    "collectCount": 10,
    "commentCount": 1,
    "hashtags": [
      { "id": "183145", "name": "ai" },
      { "id": "4278", "name": "college" },
      { "id": "192512", "name": "students" },
      { "id": "1621382854945957", "name": "studytok" },
      { "id": "1139721", "name": "hacks" }
    ],
    "mentions": [],
    "searchQuery": "chatGPT"
  }
];

// 测试清洗功能
console.log('='.repeat(50));
console.log('🧪 TikTok 数据清洗测试');
console.log('='.repeat(50));

const scraper = new TikTokScraper({
  filters: {
    minPlayCount: 100000,  // 播放量小于10万直接丢弃
    minDiggCount: 50,
    minShareCount: 0,
    languages: []
  }
});

// 加载测试数据
scraper.rawData = testData;

console.log(`\n📥 原始数据: ${scraper.rawData.length} 条`);

// 执行清洗和筛选
scraper.cleanAndFilter();

console.log(`✨ 筛选后数据: ${scraper.filteredData.length} 条`);

// 输出清洗后的数据
console.log('\n📋 清洗后的数据样本:');
scraper.filteredData.forEach((item, index) => {
  console.log(`\n--- 视频 ${index + 1} ---`);
  console.log(`ID: ${item.id}`);
  console.log(`文案: ${item.text.substring(0, 50)}...`);
  console.log(`时长: ${item.videoMeta.duration}s`);
  console.log(`播放: ${item.playCount.toLocaleString()}`);
  console.log(`点赞: ${item.diggCount.toLocaleString()}`);
  console.log(`分享: ${item.shareCount.toLocaleString()}`);
  console.log(`作者: ${item.authorMeta.nickName} (粉丝: ${item.authorMeta.fans.toLocaleString()})`);
  console.log(`视频链接: ${item.videoMeta.downloadAddr}`);
});

// 统计信息
const stats = scraper.getStatistics();
console.log('\n' + '='.repeat(50));
console.log('📊 统计信息:');
console.log('='.repeat(50));
console.log(`总视频数: ${stats.totalVideos}`);
console.log(`总播放: ${stats.totalPlays.toLocaleString()}`);
console.log(`总点赞: ${stats.totalDiggs.toLocaleString()}`);
console.log(`平均播放: ${stats.avgPlayCount.toLocaleString()}`);
console.log(`平均点赞: ${stats.avgDiggCount.toLocaleString()}`);

// 保存测试结果
scraper.exportToJson('test_output.json', scraper.filteredData);

console.log('\n✅ 测试完成!');
