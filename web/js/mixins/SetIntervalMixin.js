//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
const SetIntervalMixin = {
    componentWillMount() {
        this.intervals = [];
    },
    setInterval() {
        this.intervals.push(setInterval(...arguments));
    },
    componentWillUnmount() {
        this.intervals.forEach(clearInterval);
    }
};

export default SetIntervalMixin;
