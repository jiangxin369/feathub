/*
 * Copyright 2022 The FeatHub Authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.alibaba.feathub.flink.udf.aggregation;

import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.table.types.DataType;
import org.apache.flink.util.Preconditions;

import java.util.Iterator;
import java.util.LinkedList;

import static com.alibaba.feathub.flink.udf.aggregation.AggFuncUtils.insertIntoSortedList;
import static com.alibaba.feathub.flink.udf.aggregation.AggFuncUtils.mergeSortedLists;

/**
 * Aggregation function decorator that only aggregates up to `limit` number of most recent records.
 */
public class AggFuncWithLimit<IN_T, OUT_T, ACC_T>
        implements AggFunc<IN_T, OUT_T, AggFuncWithLimit.RawDataAccumulator<IN_T>> {
    private final AggFunc<IN_T, OUT_T, ACC_T> aggFunc;
    private final long limit;

    public AggFuncWithLimit(AggFunc<IN_T, OUT_T, ACC_T> aggFunc, long limit) {
        this.aggFunc = aggFunc;
        this.limit = limit;
    }

    @Override
    public void add(RawDataAccumulator<IN_T> acc, IN_T value, long timestamp) {
        if (acc.rawDataList.isEmpty() || timestamp >= acc.rawDataList.getLast().f1) {
            acc.rawDataList.add(Tuple2.of(value, timestamp));
            return;
        }

        insertIntoSortedList(
                acc.rawDataList, Tuple2.of(value, timestamp), (o1, o2) -> (int) (o1.f1 - o2.f1));
    }

    @Override
    public void merge(RawDataAccumulator<IN_T> target, RawDataAccumulator<IN_T> source) {
        if (source.rawDataList.isEmpty()) {
            return;
        }

        if (target.rawDataList.isEmpty()) {
            target.rawDataList.addAll(source.rawDataList);
            return;
        }

        target.rawDataList =
                mergeSortedLists(
                        target.rawDataList, source.rawDataList, (o1, o2) -> (int) (o1.f1 - o2.f1));
    }

    @Override
    public void retract(RawDataAccumulator<IN_T> accumulator, IN_T value) {
        Preconditions.checkState(
                accumulator.rawDataList.getFirst().f0.equals(value),
                "Value must be retracted by the ordered as they added to the AggFuncWithLimit.");
        accumulator.rawDataList.removeFirst();
    }

    @Override
    public void retractAccumulator(
            RawDataAccumulator<IN_T> target, RawDataAccumulator<IN_T> source) {
        for (Tuple2<IN_T, Long> value : source.rawDataList) {
            Preconditions.checkState(
                    target.rawDataList.getFirst().equals(value),
                    "Value must be retracted by the order as they added to the AggFuncWithLimit.");
            target.rawDataList.removeFirst();
        }
    }

    @Override
    public RawDataAccumulator<IN_T> createAccumulator() {
        return new RawDataAccumulator<>();
    }

    @Override
    public TypeInformation getAccumulatorTypeInformation() {
        return Types.POJO(RawDataAccumulator.class);
    }

    @Override
    public OUT_T getResult(RawDataAccumulator<IN_T> accumulator) {
        ACC_T acc = aggFunc.createAccumulator();

        Iterator<Tuple2<IN_T, Long>> iterator = accumulator.rawDataList.descendingIterator();
        long count = 0;
        while (count < limit && iterator.hasNext()) {
            count++;
            Tuple2<IN_T, Long> data = iterator.next();
            aggFunc.add(acc, data.f0, data.f1);
        }

        return aggFunc.getResult(acc);
    }

    @Override
    public DataType getResultDatatype() {
        return aggFunc.getResultDatatype();
    }

    /** Accumulator that collects raw data and their timestamps. */
    public static class RawDataAccumulator<T> {
        public LinkedList<Tuple2<T, Long>> rawDataList = new LinkedList<>();
    }
}
