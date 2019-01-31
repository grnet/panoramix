import { set } from '@ember/object';
import { typeOf } from '@ember/utils';

export function updateObject(target, source, removeMissing) {
  let targetKeys = Object.keys(target);
  let sourceKeys = Object.keys(source);
  sourceKeys.forEach((key) => {
    let targetVal = target[key];
    let sourceVal = source[key];
    let targetType = typeOf(targetVal);
    let sourceType = typeOf(sourceVal);

    if (targetType != sourceType) {
      set(target, key, sourceVal);
    } else if (targetType == "object") {
      updateObject(targetVal, sourceVal, removeMissing);
    } else if (targetType == "array") {
      updateObject(targetVal, sourceVal, removeMissing);
    } else if (targetVal != sourceVal) {
      set(target, key, sourceVal);
    }
  });

  if (removeMissing) {
    targetKeys.forEach((key) => {
      if (!sourceKeys.includes(key)) {
        delete target[key];
      }
    });
  }
}
