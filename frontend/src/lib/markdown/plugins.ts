import rehypeKatex from 'rehype-katex'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'

export const markdownRemarkPlugins = [remarkGfm, remarkMath]
export const markdownRehypePlugins = [rehypeRaw, rehypeKatex]
