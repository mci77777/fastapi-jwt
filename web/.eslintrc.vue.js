// .eslintrc.vue.js
// Vue 3 + Naive UI ESLint 配置 - 防止 JSX 语法混入

module.exports = {
  extends: ['@zclzone', '@unocss', '.eslint-global-variables.json'],
  rules: {
    // ========================================
    // 防止 JSX 语法混入 Vue 模板
    // ========================================

    // 禁止在 .vue 文件中使用 JSX
    'vue/no-jsx-component-name': 'error',

    // 禁止使用 className 属性（应使用 class 或 :class）
    'vue/no-reserved-component-names': [
      'error',
      {
        disallowVueBuiltInComponents: true,
        disallowVue3BuiltInComponents: true,
      },
    ],

    // 强制使用 Vue 指令而非 JSX 语法
    'vue/prefer-template': 'error',

    // ========================================
    // Vue 3 Composition API 最佳实践
    // ========================================

    // 强制使用 <script setup>
    'vue/component-api-style': ['error', ['script-setup']],

    // 强制 defineOptions 中的 name 使用 PascalCase
    'vue/component-definition-name-casing': ['error', 'PascalCase'],

    // 禁止在 computed 中产生副作用
    'vue/no-side-effects-in-computed-properties': 'error',

    // 禁止在模板中使用 this
    'vue/this-in-template': ['error', 'never'],

    // ========================================
    // 模板语法规范
    // ========================================

    // 强制 v-for 必须有 :key
    'vue/require-v-for-key': 'error',

    // 禁止 v-if 和 v-for 同级使用
    'vue/no-use-v-if-with-v-for': [
      'error',
      {
        allowUsingIterationVar: false,
      },
    ],

    // 强制组件事件使用 kebab-case
    'vue/custom-event-name-casing': ['error', 'kebab-case'],

    // 强制 v-bind 指令样式
    'vue/v-bind-style': ['error', 'shorthand'],

    // 强制 v-on 指令样式
    'vue/v-on-style': ['error', 'shorthand'],

    // ========================================
    // Props 和 Emit 规范
    // ========================================

    // 禁止直接修改 props
    'vue/no-mutating-props': 'error',

    // 强制 props 使用 camelCase
    'vue/prop-name-casing': ['error', 'camelCase'],

    // ========================================
    // 代码质量
    // ========================================

    // 禁止重复的属性
    'vue/no-duplicate-attributes': [
      'error',
      {
        allowCoexistClass: true,
        allowCoexistStyle: true,
      },
    ],

    // 禁止未使用的组件
    'vue/no-unused-components': [
      'warn',
      {
        ignoreWhenBindingPresent: true,
      },
    ],

    // 禁止未使用的变量
    'vue/no-unused-vars': [
      'warn',
      {
        ignorePattern: '^_',
      },
    ],

    // 强制组件名称多词
    'vue/multi-word-component-names': [
      'error',
      {
        ignores: ['index'],
      },
    ],

    // ========================================
    // 性能优化
    // ========================================

    // 警告复杂的模板表达式
    'vue/no-template-shadow': 'warn',

    // 建议使用简写语法
    'vue/prefer-separate-static-class': 'warn',

    // ========================================
    // Naive UI 特定规范
    // ========================================

    // 确保 Naive UI 组件正确导入
    'no-restricted-imports': [
      'error',
      {
        patterns: [
          {
            group: ['naive-ui'],
            message: '请从 naive-ui 按需导入组件，例如: import { NButton } from "naive-ui"',
          },
        ],
      },
    ],

    // ========================================
    // 可访问性
    // ========================================

    // 强制 img 标签有 alt 属性
    'vue/require-valid-default-prop': 'error',

    // 强制按钮类型
    'vue/html-button-has-type': [
      'warn',
      {
        button: true,
        submit: true,
        reset: true,
      },
    ],
  },

  overrides: [
    {
      // .vue 文件特定规则
      files: ['*.vue'],
      rules: {
        // 禁止在 template 中使用 JSX 语法
        'no-restricted-syntax': [
          'error',
          {
            selector: 'JSXElement',
            message: '禁止在 .vue 文件的 <template> 中使用 JSX 语法。请使用 Vue 模板语法。',
          },
          {
            selector: 'JSXFragment',
            message: '禁止在 .vue 文件中使用 JSX Fragment。请使用 Vue 模板语法。',
          },
        ],
      },
      parser: 'vue-eslint-parser',
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: {
          jsx: false, // 禁用 JSX 解析
        },
      },
    },
    {
      // <script setup> 特定规则
      files: ['*.vue'],
      rules: {
        // 允许在 setup 中使用顶层 await
        'no-restricted-syntax': [
          'error',
          {
            selector: 'ForInStatement',
            message: 'for..in 循环会迭代原型链，请使用 for..of 或 Object.keys()',
          },
        ],
      },
    },
  ],
}
