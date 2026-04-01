/**
 * TikTok Scraper - Main Entry
 * 使用 Apify API 爬取 TikTok 数据，清洗，筛选，并导出为 JSON
 */

require('dotenv').config();
const fs = require('fs');
const path = require('path');
const ApifyClient = require('apify-client');

// ============== 配置 ==============
const CONFIG = {
  // Apify API Token (从环境变量读取)
  apifyToken: process.env.APIFY_TOKEN || '',
  
  // Actor ID
  actorId: 'GdWCkxBtKWOsKjdch',
  resultsPerKeyword: 8,
  
  // 默认爬取参数
  defaultParams: {
    commentsPerPost: 0,
    excludePinnedPosts: false,
    maxFollowersPerProfile: 0,
    maxFollowingPerProfile: 0,
    maxRepliesPerComment: 0,
    proxyCountryCode: 'None',
    resultsPerPage: 20,
    scrapeRelatedVideos: false,
    searchDatePosted: '1',
    searchSection: '/video',
    searchSorting: '0',
    shouldDownloadAvatars: false,
    shouldDownloadCovers: false,
    shouldDownloadMusicCovers: false,
    shouldDownloadSlideshowImages: false,
    shouldDownloadVideos: false  // 默认不下载视频，节省空间
  },
  
  // 数据存储路径
  dataDir: path.join(__dirname, '..', 'data'),
  
  // 筛选阈值
  filters: {
    minPlayCount: 0,
    minDiggCount: 0,
    minShareCount: 0,
    languages: []  // 空数组表示不限制语言
  }
};

// ============== 核心类 ==============

class TikTokScraper {
  constructor(config = {}) {
    this.config = { ...CONFIG, ...config };
    this.client = null;
    this.rawData = [];
    this.filteredData = [];
    
    // 确保数据目录存在
    if (!fs.existsSync(this.config.dataDir)) {
      fs.mkdirSync(this.config.dataDir, { recursive: true });
    }
  }

  /**
   * 初始化 Apify 客户端
   */
  initClient() {
    if (!this.config.apifyToken) {
      throw new Error('请设置 APIFY_TOKEN 环境变量或在配置中指定');
    }
    this.client = new ApifyClient({
      token: this.config.apifyToken
    });
  }

  /**
   * 执行爬取任务
   * @param {Array<string>} queries - 搜索关键词数组
   * @param {Object} customParams - 自定义参数
   */
  async scrape(queries, customParams = {}) {
    // 如果传入了 queries 参数则使用，否则使用 params 中的 searchQueries
    console.log(`🚀 开始爬取 TikTok...`);
    
    if (!this.client) {
      this.initClient();
    }

    // 使用自定义参数（如果传入），否则使用配置文件中的 customParams
    const params = {
      ...this.config.defaultParams,
      ...(this.config.customParams || {}),
      ...(customParams && Object.keys(customParams).length > 0 ? customParams : {})
    };
    
    // 如果传入了 queries 参数则使用，否则使用 params 中的 searchQueries
    const finalQueries = (queries && queries.length > 0) 
      ? queries 
      : (params.searchQueries || []);
    const normalizedQueries = finalQueries
      .map(query => String(query || '').trim())
      .filter(Boolean);
    
    if (normalizedQueries.length === 0) {
      throw new Error('未提供有效的搜索关键词');
    }

    console.log(`🔍 关键词: ${normalizedQueries.join(', ')}`);

    try {
      this.rawData = [];
      const seenVideoIds = new Set();
      let duplicateCount = 0;

      for (const [index, query] of normalizedQueries.entries()) {
        const runParams = {
          ...params,
          searchQueries: [query],
          resultsPerPage: this.config.resultsPerKeyword
        };

        console.log(`\n🔁 [${index + 1}/${normalizedQueries.length}] 抓取关键词: ${query}`);
        console.log('📡 正在调用 Apify API...');
        console.log('📋 请求参数:', JSON.stringify(runParams, null, 2));

        const run = await this.client.actor(this.config.actorId).call(runParams);
        console.log('✅ 任务完成，获取数据集...');

        const listResult = await this.client.dataset(run.defaultDatasetId).listItems();
        const items = listResult.items || [];

        let addedCount = 0;
        for (const item of items) {
          const videoId = item?.id;
          if (videoId && seenVideoIds.has(videoId)) {
            duplicateCount++;
            continue;
          }
          if (videoId) {
            seenVideoIds.add(videoId);
          }
          this.rawData.push(item);
          addedCount++;
        }

        console.log(`📥 关键词 "${query}" 抓取 ${items.length} 条，去重后新增 ${addedCount} 条`);
      }

      console.log(`📥 原始数据累计: ${this.rawData.length} 条`);
      if (duplicateCount > 0) {
        console.log(`♻️ 按视频ID去重移除: ${duplicateCount} 条`);
      }
      
      // 保存原始数据
      this.saveRawData(normalizedQueries);
      
      // 清洗和筛选数据
      this.cleanAndFilter();
      
      // 保存清洗后的数据
      this.saveFilteredData(normalizedQueries);
      
      return {
        rawCount: this.rawData.length,
        filteredCount: this.filteredData.length,
        data: this.filteredData
      };
      
    } catch (error) {
      console.error('❌ 爬取失败:', error.message);
      throw error;
    }
  }

  /**
   * 从本地文件加载已有数据
   * @param {string} filename - 文件名
   */
  loadFromFile(filename) {
    const filepath = path.join(this.config.dataDir, filename);
    if (fs.existsSync(filepath)) {
      const data = JSON.parse(fs.readFileSync(filepath, 'utf-8'));
      this.rawData = data;
      return data;
    }
    return [];
  }

  /**
   * 清洗和筛选数据
   */
  cleanAndFilter() {
    console.log('🧹 正在清洗和筛选数据...');
    
    this.filteredData = this.rawData
      .map(item => this.cleanItem(item))
      .filter(item => this.filterItem(item));
    
    console.log(`✨ 筛选后数据: ${this.filteredData.length} 条`);
  }

  /**
   * 清洗单条数据 - 只保留需要的字段
   * @param {Object} item - 原始数据项
   */
  cleanItem(item) {
    return {
      // 视频ID
      id: item.id || '',
      
      // 视频文案
      text: item.text || '',
      textLanguage: item.textLanguage || 'unknown',
      hashtags: Array.isArray(item.hashtags) ? item.hashtags : [],
      
      // 互动数据
      diggCount: item.diggCount || 0,
      shareCount: item.shareCount || 0,
      playCount: item.playCount || 0,
      
      // 视频元数据
      videoMeta: {
        duration: item.videoMeta?.duration || 0,
        downloadAddr: item.videoMeta?.downloadAddr || '',
        webVideoUrl: item.webVideoUrl || ''
      },
      
      // 作者信息
      authorMeta: {
        nickName: item.authorMeta?.nickName || '',
        fans: item.authorMeta?.fans || 0
      },
      
      // 发布日期
      createTime: item.createTime || '',
      createTimeISO: item.createTimeISO || ''
    };
  }

  /**
   * 筛选数据
   * @param {Object} item - 清洗后的数据项
   */
  filterItem(item) {
    const filters = this.config.filters;
    
    // 播放量筛选
    if (item.playCount < filters.minPlayCount) {
      return false;
    }
    
    // 点赞数筛选
    if (item.diggCount < filters.minDiggCount) {
      return false;
    }
    
    // 分享数筛选
    if (item.shareCount < filters.minShareCount) {
      return false;
    }
    
    // 语言筛选
    if (filters.languages && filters.languages.length > 0) {
      if (!filters.languages.includes(item.textLanguage)) {
        return false;
      }
    }
    
    return true;
  }

  /**
   * 保存原始数据到 data/raw/ 文件夹
   * @param {Array<string>} queries - 搜索关键词
   */
  saveRawData(queries) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const queryStr = (queries && queries.length > 0) ? queries.join('_') : 'data';
    const filename = `raw_${queryStr}_${timestamp}.json`;
    
    // 保存到 data/raw/ 文件夹
    const rawDir = path.join(this.config.dataDir, 'raw');
    if (!fs.existsSync(rawDir)) {
      fs.mkdirSync(rawDir, { recursive: true });
    }
    const filepath = path.join(rawDir, filename);
    
    fs.writeFileSync(filepath, JSON.stringify(this.rawData, null, 2), 'utf-8');
    console.log(`💾 原始数据已保存: ${filename}`);
    
    return filename;
  }

  /**
   * 保存筛选后的数据到 filtered-result.json
   * @param {Array<string>} queries - 搜索关键词
   */
  saveFilteredData(queries) {
    // 导出 filtered-result.json
    const filepath = path.join(this.config.dataDir, 'filtered-result.json');
    fs.writeFileSync(filepath, JSON.stringify(this.filteredData, null, 2), 'utf-8');
    console.log(`💾 筛选结果已导出: filtered-result.json (${this.filteredData.length} 条)`);
    
    return 'filtered-result.json';
  }

  /**
   * 导出到指定格式的 JSON 文件
   * @param {string} filename - 文件名
   * @param {Array<Object>} data - 数据
   */
  exportToJson(filename, data) {
    const filepath = path.join(this.config.dataDir, filename);
    fs.writeFileSync(filepath, JSON.stringify(data, null, 2), 'utf-8');
    console.log(`📤 已导出: ${filename}`);
    return filepath;
  }

  /**
   * 获取数据统计
   */
  getStatistics() {
    if (!this.filteredData || this.filteredData.length === 0) {
      return null;
    }

    const stats = {
      totalVideos: this.filteredData.length,
      totalPlays: 0,
      totalDiggs: 0,
      totalShares: 0,
      avgPlayCount: 0,
      avgDiggCount: 0,
      topAuthors: [],
      languageDistribution: {},
      hashtagFrequency: {}
    };

    this.filteredData.forEach(item => {
      stats.totalPlays += item.playCount;
      stats.totalDiggs += item.diggCount;
      stats.totalShares += item.shareCount;
      
      // 语言分布
      const lang = item.textLanguage || 'unknown';
      stats.languageDistribution[lang] = (stats.languageDistribution[lang] || 0) + 1;
      
      // 标签频率
      const hashtags = Array.isArray(item.hashtags) ? item.hashtags : [];
      hashtags.forEach(tag => {
        stats.hashtagFrequency[tag] = (stats.hashtagFrequency[tag] || 0) + 1;
      });
    });

    stats.avgPlayCount = Math.round(stats.totalPlays / this.filteredData.length);
    stats.avgDiggCount = Math.round(stats.totalDiggs / this.filteredData.length);

    // Top 作者
    const authorCounts = {};
    this.filteredData.forEach(item => {
      const author = item.authorMeta.nickName;
      authorCounts[author] = (authorCounts[author] || 0) + item.playCount;
    });
    
    stats.topAuthors = Object.entries(authorCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, plays]) => ({ name, totalPlays: plays }));

    return stats;
  }
}

// ============== 主函数 ==============

async function main() {
  // 从命令行参数或配置文件获取配置
  const args = process.argv.slice(2);
  
  // 读取配置文件
  const configPath = path.join(__dirname, '..', 'config', 'config.json');
  let userConfig = {};
  
  if (fs.existsSync(configPath)) {
    userConfig = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  }

  // 创建爬虫实例
  const scraper = new TikTokScraper({
    apifyToken: userConfig.apifyToken || process.env.APIFY_TOKEN,
    filters: userConfig.filters || CONFIG.filters,
    customParams: userConfig.customParams,
    resultsPerKeyword: userConfig.resultsPerKeyword || CONFIG.resultsPerKeyword
  });

  // 解析命令行参数 - 不设置默认值，让 scrape 函数决定使用哪个
  const queries = userConfig.defaultQueries;
  
  console.log('='.repeat(50));
  console.log('🎵 TikTok Scraper - Greatbay Studio');
  console.log('='.repeat(50));

  try {
    // 执行爬取
    const result = await scraper.scrape(queries, userConfig.customParams);
    
    // 输出统计信息
    const stats = scraper.getStatistics();
    if (stats) {
      console.log('\n📊 数据统计:');
      console.log(`   总视频数: ${stats.totalVideos}`);
      console.log(`   总播放: ${stats.totalPlays.toLocaleString()}`);
      console.log(`   总点赞: ${stats.totalDiggs.toLocaleString()}`);
      console.log(`   平均播放: ${stats.avgPlayCount.toLocaleString()}`);
      console.log(`   平均点赞: ${stats.avgDiggCount.toLocaleString()}`);
      
      console.log('\n🌐 语言分布:');
      Object.entries(stats.languageDistribution)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .forEach(([lang, count]) => {
          console.log(`   ${lang}: ${count}`);
        });
      
      console.log('\n🏆 Top 作者:');
      stats.topAuthors.slice(0, 5).forEach((author, i) => {
        console.log(`   ${i + 1}. ${author.name}: ${author.totalPlays.toLocaleString()} 播放`);
      });
    }
    
    console.log('\n✅ 爬取完成!');
    
  } catch (error) {
    console.error('❌ 错误:', error.message);
    process.exit(1);
  }
}

// 导出模块
module.exports = { TikTokScraper, CONFIG };

// 如果直接运行
if (require.main === module) {
  main();
}
