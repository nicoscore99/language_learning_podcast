import {staticFile} from 'remotion';

export const mediaSource = (src: string) => {
  if (/^[A-Za-z]:[\\/]/.test(src)) {
    return `file:///${src.replace(/\\/g, '/')}`;
  }

  if (/^(https?:|file:|data:|\/)/.test(src)) {
    return src;
  }

  return staticFile(src);
};
