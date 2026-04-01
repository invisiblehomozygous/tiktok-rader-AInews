/**
 * X (Twitter) Scraper - Main Entry
 * 使用 Apify API 爬取 X (Twitter) 数据，清洗，筛选，并导出为 JSON
 */

require('dotenv').config();
const fs = require('fs');
const path = require('path');
const apify = require('apify-client');
const ApifyClient = apify.ApifyClient;

// ============== 配置 ==============
const CONFIG = {
  // Apify API Token (从环境变量读取)
  apifyToken: process.env.APIFY_TOKEN || '',
  
  // Actor ID - X Scraper
  actorId: 'CJdippxWmn9uRfooo',
  
  // 数据存储路径
  dataDir: path.join(__dirname, '..', 'data'),
  
  // 筛选阈值
  filters: {
    maxHoursAgo: 36,
    minViewCount: 500000
  }
};

// ============== 核心类 ==============

class XScraper {
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
      throw new Error('请设置 APIFY_TOKEN 环境变量');
    }
    this.client = new ApifyClient({
      token: this.config.apifyToken
    });
  }

  /**
   * 执行爬取任务
   * @param {Object} customParams - 自定义参数
   */
  async scrape(customParams = {}) {
    console.log(`🚀 开始爬取 X (Twitter)...`);
    
    if (!this.client) {
      this.initClient();
    }

    // 使用自定义参数（如果传入），否则使用配置文件中的 customParams
    const params = customParams && Object.keys(customParams).length > 0 
      ? customParams 
      : this.config.customParams;
    
    console.log('📡 正在调用 Apify API...');
    console.log('📋 请求参数:', JSON.stringify(params, null, 2));
    
    try {
      // 启动 Actor
      const run = await this.client.actor(this.config.actorId).call(params);
      
      console.log(`✅ 任务完成，获取数据集...`);
      
      // 获取结果 - 使用 listItems API
      this.rawData = [];
      const listResult = await this.client.dataset(run.defaultDatasetId).listItems();
      this.rawData = listResult.items || [];
      
      console.log(`📥 原始数据: ${this.rawData.length} 条`);
      
      // 保存原始数据
      this.saveRawData();
      
      // 清洗和筛选数据
      this.cleanAndFilter();
      
      // 保存筛选后的数据
      this.saveFilteredData();
      
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
      // 推文ID
      id: item.id || '',
      
      // 链接
      url: item.url || '',
      
      // 推文内容
      text: item.text || '',
      
      // 发布时间
      createdAt: item.createdAt || '',
      
      // 互动数据
      likeCount: item.likeCount || 0,
      viewCount: item.viewCount || 0
    };
  }

  /**
   * 筛选数据
   * @param {Object} item - 清洗后的数据项
   */
  filterItem(item) {
    const filters = this.config.filters;
    
    // 时间筛选 - 36小时内
    if (item.createdAt) {
      const itemTime = new Date(item.createdAt);
      const now = new Date();
      const hoursDiff = (now - itemTime) / (1000 * 60 * 60);
      
      if (hoursDiff > filters.maxHoursAgo) {
        return false;
      }
    }
    
    // 观看量筛选 - 超过50万
    if (item.viewCount < filters.minViewCount) {
      return false;
    }
    
    return true;
  }

  /**
   * 保存原始数据到 data/raw/ 文件夹
   */
  saveRawData() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `raw_${timestamp}.json`;
    
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
   */
  saveFilteredData() {
    // 导出 filtered-result.json
    const filepath = path.join(this.config.dataDir, 'filtered-result.json');
    fs.writeFileSync(filepath, JSON.stringify(this.filteredData, null, 2), 'utf-8');
    console.log(`💾 筛选结果已导出: filtered-result.json (${this.filteredData.length} 条)`);
    
    return 'filtered-result.json';
  }

  /**
   * 获取数据统计
   */
  getStatistics() {
    if (!this.filteredData || this.filteredData.length === 0) {
      return null;
    }

    return {
      totalTweets: this.filteredData.length,
      totalViews: this.filteredData.reduce((sum, t) => sum + t.viewCount, 0),
      totalLikes: this.filteredData.reduce((sum, t) => sum + t.likeCount, 0),
      avgViewCount: Math.round(this.filteredData.reduce((sum, t) => sum + t.viewCount, 0) / this.filteredData.length),
      avgLikeCount: Math.round(this.filteredData.reduce((sum, t) => sum + t.likeCount, 0) / this.filteredData.length)
    };
  }
}

// ============== 主函数 ==============

async function main() {
  const configPath = path.join(__dirname, '..', 'config', 'config.json');
  let userConfig = {};
  
  if (fs.existsSync(configPath)) {
    userConfig = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  }

  const scraper = new XScraper({
    filters: userConfig.filters || CONFIG.filters
  });

  console.log('='.repeat(50));
  console.log('🐦 X Scraper - Greatbay Studio');
  console.log('='.repeat(50));

  try {
    const result = await scraper.scrape(userConfig.customParams);
    
    const stats = scraper.getStatistics();
    if (stats) {
      console.log('\n📊 数据统计:');
      console.log(`   总推文数: ${stats.totalTweets}`);
      console.log(`   总观看: ${stats.totalViews.toLocaleString()}`);
      console.log(`   总点赞: ${stats.totalLikes.toLocaleString()}`);
      console.log(`   平均观看: ${stats.avgViewCount.toLocaleString()}`);
      console.log(`   平均点赞: ${stats.avgLikeCount.toLocaleString()}`);
    }
    
    console.log('\n✅ 爬取完成!');
    
  } catch (error) {
    console.error('❌ 错误:', error.message);
    process.exit(1);
  }
}

// 导出模块
module.exports = { XScraper, CONFIG };

// 如果直接运行
if (require.main === module) {
  main();
}
