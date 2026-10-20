import {defineConfig} from '@playwright/test'
export default defineConfig({testDir:'./tests',timeout:45000,workers:1,use:{baseURL:process.env.WORKSPACE_TEST_URL || 'http://127.0.0.1:5174',viewport:{width:1440,height:1000},headless:true,screenshot:'only-on-failure',launchOptions:{channel:'chrome'}},outputDir:'../storage/browser-results',reporter:'list'})
