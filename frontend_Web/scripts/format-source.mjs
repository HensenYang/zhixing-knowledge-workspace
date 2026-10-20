import fs from 'node:fs'
import path from 'node:path'
import {parse} from '@babel/parser'
import generator from '@babel/generator'
const generate=generator.default || generator
function format(directory){for(const item of fs.readdirSync(directory,{withFileTypes:true})){const name=path.join(directory,item.name);if(item.isDirectory())format(name);else if(/\.(jsx|js)$/.test(name)){const tree=parse(fs.readFileSync(name,'utf8'),{sourceType:'module',plugins:['jsx']});fs.writeFileSync(name,generate(tree,{comments:true,compact:false}).code+'\n')}}}
format('src')
