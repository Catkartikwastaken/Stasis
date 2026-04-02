import fs from 'fs';
const path = '../server/public/index.html';
let content = fs.readFileSync(path, 'utf8');
content = content.replace('type="module" crossorigin>', 'defer>');
fs.writeFileSync(path, content);
console.log('Final build patched successfully.');
