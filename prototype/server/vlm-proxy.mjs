#!/usr/bin/env node
/**
 * 喵汪小镇 · 视觉大模型（VLM）结构化 DNA 提取本地代理 (server/vlm-proxy.mjs)
 * =========================================================================
 * 接收最多 8 张猫咪照片，转发至 OpenAI 兼容视觉大模型接口（通义千问 VL / 豆包 / GPT-4o），
 * 按严格的 JSON Schema 输出底色、花色类型、调色板、眼睛/鼻头颜色、6 个形态键、语义印记列表与正脸关键点。
 * API Key 保存在服务端环境变量（VLM_API_KEY / OPENAI_API_KEY），绝不暴露到浏览器。
 */

import http from 'node:http';

const PORT = Number(process.env.PORT || 8787);
const VLM_BASE_URL = process.env.VLM_BASE_URL || 'https://api.openai.com/v1/chat/completions';
const VLM_MODEL = process.env.VLM_MODEL || 'gpt-4o';
const API_KEY = process.env.VLM_API_KEY || process.env.OPENAI_API_KEY || '';

export const VLM_SYSTEM_PROMPT = `你是一位专业的猫咪外观与像素美术 DNA 提取专家。
用户会提供同一只猫的最多 8 张不同角度真实照片（正脸、侧卧、揣手、仰躺翻肚皮、俯视背脊等）。
请交叉比对全部照片，输出严格符合 JSON Schema 的结构化猫咪 DNA 数据。

【最重要铁律：左右方向约定】
- 所有 region 中的 left / right 恒指【猫自身的左（+X）和猫自身的右（-X）】！
- 当观察正脸照片时：画面左侧 = 猫自身的右侧（muzzle.right / paw.frontRight / eyeR）；画面右侧 = 猫自身的左侧（muzzle.left / paw.frontLeft / eyeL）。
- 必须结合多张照片交叉确认非对称特征（例如：鼻梁白火焰偏向哪只眼、左右嘴套哪边有焦糖色块哪边是窄唇边、哪只前腿腕部内侧有色斑、左肋还是右肋有白云斑、雪白肚皮中央是否有独立暖橘斑）。

【允许使用的语义区域 region 枚举】
- "body.tabby_stripes" | "back.dorsal_stripe" | "back.saddle"
- "head.crown_stripes" | "forehead.m_tabby"
- "nose_bridge.blaze_left" | "nose_bridge.blaze_center"
- "muzzle.base_white" | "muzzle.right" | "muzzle.right_whisker_dots" | "muzzle.left" | "muzzle.left_lip" | "chin"
- "chest.bib" | "belly.base" | "belly.center_spot"
- "flank.left" | "flank.right"
- "paw.frontLeft" | "paw.frontRight" | "paw.frontRight.inner_wrist"
- "paw.hindLeft.thigh" | "paw.hindLeft.sock" | "paw.hindRight.thigh" | "paw.hindRight.sock"
- "ear.left" | "ear.right" | "tail.rings" | "tail.solid" | "tail.tip"`;

export const DNA_JSON_SCHEMA = {
  name: 'photo_extracted_cat_dna',
  strict: true,
  schema: {
    type: 'object',
    required: [
      'id',
      'name',
      'coatPattern',
      'baseColor',
      'palette',
      'earInner',
      'eyes',
      'nose',
      'shape',
      'semanticMarkings',
      'faceKeypoints',
    ],
    additionalProperties: false,
    properties: {
      id: { type: 'string' },
      name: { type: 'string' },
      coatPattern: {
        type: 'string',
        enum: ['tabby_and_white', 'orange_tabby', 'bicolor_tuxedo', 'calico', 'solid'],
      },
      baseColor: { type: 'string' },
      palette: { type: 'array', items: { type: 'string' } },
      earInner: { type: 'string' },
      eyes: {
        type: 'object',
        required: ['iris', 'pupil'],
        additionalProperties: false,
        properties: { iris: { type: 'string' }, pupil: { type: 'string' } },
      },
      nose: { type: 'string' },
      shape: {
        type: 'object',
        required: ['headRound', 'weight', 'earSize', 'tailFluff', 'cheekFluff', 'muzzleSize'],
        additionalProperties: false,
        properties: {
          headRound: { type: 'number' },
          weight: { type: 'number' },
          earSize: { type: 'number' },
          tailFluff: { type: 'number' },
          cheekFluff: { type: 'number' },
          muzzleSize: { type: 'number' },
        },
      },
      semanticMarkings: {
        type: 'array',
        items: {
          type: 'object',
          required: ['id', 'label', 'region', 'color', 'extent'],
          additionalProperties: false,
          properties: {
            id: { type: 'string' },
            label: { type: 'string' },
            region: { type: 'string' },
            color: { type: 'string' },
            secondaryColor: { type: 'string' },
            extent: { type: 'string', enum: ['small', 'medium', 'large', 'full'] },
            connectsTo: { type: 'array', items: { type: 'string' } },
          },
        },
      },
      faceKeypoints: {
        type: 'object',
        required: [
          'eyeR',
          'eyeL',
          'nose',
          'blazeTop',
          'mouthR',
          'mouthL',
          'chin',
          'forehead',
          'earBaseR',
          'earBaseL',
        ],
        additionalProperties: false,
        properties: {
          eyeR: { type: 'array', items: { type: 'number' } },
          eyeL: { type: 'array', items: { type: 'number' } },
          nose: { type: 'array', items: { type: 'number' } },
          blazeTop: { type: 'array', items: { type: 'number' } },
          mouthR: { type: 'array', items: { type: 'number' } },
          mouthL: { type: 'array', items: { type: 'number' } },
          chin: { type: 'array', items: { type: 'number' } },
          forehead: { type: 'array', items: { type: 'number' } },
          earBaseR: { type: 'array', items: { type: 'number' } },
          earBaseL: { type: 'array', items: { type: 'number' } },
        },
      },
    },
  },
};

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method === 'POST' && req.url === '/api/extract-dna') {
    let body = '';
    for await (const chunk of req) body += chunk;
    try {
      const payload = JSON.parse(body || '{}');
      const photos = (payload.photos || []).slice(0, 8);

      if (!API_KEY) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            fallback: true,
            message: '未配置 VLM_API_KEY，前端自动使用内置 8 张真照片校准提取器 + 正脸实拍关键点投影。',
          }),
        );
        return;
      }

      const content = [
        {
          type: 'text',
          text: `请根据以下 ${photos.length} 张照片提取这只猫（名称：${payload.petName || '咪咪'}）的结构化 DNA JSON。注意左右恒为猫自身的左右！`,
        },
        ...photos.map((url) => ({
          type: 'image_url',
          image_url: { url },
        })),
      ];

      const upstream = await fetch(VLM_BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${API_KEY}`,
        },
        body: JSON.stringify({
          model: VLM_MODEL,
          messages: [
            { role: 'system', content: VLM_SYSTEM_PROMPT },
            { role: 'user', content },
          ],
          response_format: { type: 'json_schema', json_schema: DNA_JSON_SCHEMA },
          temperature: 0.1,
        }),
      });

      const data = await upstream.json();
      const rawJson = data?.choices?.[0]?.message?.content;
      const extracted = typeof rawJson === 'string' ? JSON.parse(rawJson) : data;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ fallback: false, extracted }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(err) }));
    }
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not Found' }));
});

if (import.meta.url === `file://${process.argv[1]}`) {
  server.listen(PORT, () => {
    console.log(`[vlm-proxy] Listening on http://localhost:${PORT}/api/extract-dna (model=${VLM_MODEL})`);
  });
}
