import { helper } from '@ember/component/helper';
import { typeOf } from '@ember/utils';

export function docParams([doc, root, key, value, meta]) {
  let type = typeOf(value);
  if (meta && meta.hasOwnProperty('type')) { type = meta.type; }
  let isDoc = ['array', 'object', 'dict'].includes(type);
  let path = [root, key].join('/');
  return {
    value, key, isDoc, path, root, type
  }
}

export default helper(docParams);
