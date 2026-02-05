/**
 * RagPage - Compound Component 진입점
 * 사용법: <RagPage.Provider><RagPage.Layout>...</RagPage.Layout></RagPage.Provider>
 */

'use client';

import { RagPageProvider } from './Context';
import Layout from './Layout';
import Main from './Main';
import Header from './Header';
import Content, { ContentInner } from './Content';
import Question from './Question';
import Answer from './Answer';
import Input from './Input';
import Sidebar from './Sidebar';
import Indicator from './Indicator';

const RagPage = {
  Provider: RagPageProvider,
  Layout,
  Main,
  Header,
  Content,
  ContentInner,
  Input,
  Question,
  Answer,
  Sidebar,
  Indicator,
};

export default RagPage;
