"""Shared paging rules. List responses stay plain JSON arrays; the total comes in X-Total-Count."""


def page(limit, offset, maximum):
    return min(max(limit, 1), maximum), max(offset, 0)


def set_total(response, total):
    response.headers['X-Total-Count'] = str(total)
