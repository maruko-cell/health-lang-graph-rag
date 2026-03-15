import { useCallback, useRef } from 'react'

/**
 * 生成可控制弹窗组件的 ref，并提供 open/close 便捷方法。
 *
 * 功能描述：
 * 统一封装「ref 调用式弹窗」的使用方式，返回 modalRef 供组件透传，同时返回 open/close 两个方法，
 * 以避免在业务组件内到处写可选链调用与参数透传。
 *
 * 入参说明：无入参。
 *
 * 返回值说明：
 * - {Object}：
 *   - modalRef：React ref，挂载到弹窗组件；
 *   - open：(payload?: any) => void，调用弹窗实例的 open；
 *   - close：() => void，调用弹窗实例的 close。
 *
 * 关键逻辑备注：
 * - 约定弹窗实例通过 useImperativeHandle 暴露 open/close；
 * - open 支持透传任意 payload（由具体弹窗定义数据结构）。
 *
 * @returns {{ modalRef: import('react').MutableRefObject<any>, open: (payload?: any) => void, close: () => void }}
 */
export function useModalRef() {
  const modalRef = useRef(null)

  const open = useCallback((payload) => {
    modalRef.current?.open?.(payload)
  }, [])

  const close = useCallback(() => {
    modalRef.current?.close?.()
  }, [])

  return { modalRef, open, close }
}

